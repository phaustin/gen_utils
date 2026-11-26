# Debugging a rattler-build upload to anaconda.org (401 Unauthorized), 2026-11-23

---

## Prompt 1

> the file anaconda_session.txt shows a problem I am having trying to upload a
> conda package using the api key. Upload succeeds using the anaconda api with
> the api key beginning with eyJ, but fails when I use rattler-build upload

## Response 1

I don't have a confirmed root cause yet. The log does show one concrete
difference between the run that worked and the one that failed: **they didn't
use the same token.**

- **`ana org upload` (worked)** used the token in `~/.anaconda/keyring`. That's
  the `eyJ_…` token `ana whoami` shows.
- **`rattler-build upload` (401)** used `ANACONDA_API_KEY`, which you filled
  from the macOS Keychain item `anaconda-api-key`. Nothing in the log shows that
  this is the same `eyJ_…` token. It could be an older or revoked anaconda.org
  token, or the lookup could have returned nothing.

I tried to compare the two by hash without printing them, but the permission
system blocked reads of your stored credentials. So please run these checks
yourself.

**1. Check what's actually in the environment variable** (prints only the first
4 characters and the length):

```
K=$(security find-generic-password -s anaconda-api-key -w); echo "${K:0:4} ${#K}"
```

If it doesn't start with `eyJ`, or the length is 0, that's the cause. Store the
`eyJ` token in the Keychain:

```
security add-generic-password -U -s anaconda-api-key -a "$USER" -w '<eyJ token>'
```

**2. If it is the `eyJ` token, test it against the API directly with two auth
styles:**

```
curl -s -o /dev/null -w "token:  %{http_code}\n" -H "Authorization: token $K" https://api.anaconda.org/user
curl -s -o /dev/null -w "bearer: %{http_code}\n" -H "Authorization: Bearer $K" https://api.anaconda.org/user
```

- **Both return 200:** the token is fine. Run step 3 to see what rattler-build
  sends.
- **Only `Bearer` returns 200:** rattler-build is probably sending the `token`
  form. I couldn't confirm that from its source, because the fetches of the
  upload code returned 404 (it seems to have moved). If so, it's a rattler-build
  incompatibility with the new `eyJ` keys, worth reporting to
  prefix-dev/rattler-build. Until it's fixed, `ana org upload` is the
  workaround.
- **Both return 401:** the key itself is being rejected, or it lacks the scope
  to upload.

**3. Re-run with verbose logging** to see the actual requests:

```
pixi run rattler-build upload anaconda --owner eoas_ubc --force -vvv output/noarch/*.conda
```

Add `--force` now in any case. The `ana` upload already put 0.3.1 on
anaconda.org, so without it you'd get a conflict error that hides the auth
result.

This also affects the CI job in `.github/workflows/conda-build.yml`, which runs
`rattler-build upload anaconda` with `secrets.ANACONDA_API_KEY`. It will fail
the same way until this is resolved.

---

## Prompt 2 (command run)

```
K=$(security find-generic-password -s anaconda-api-key -w); echo "${K:0:4} ${#K}"
```

Output: `eyJh 552`

## Response 2

The Keychain item holds a JWT-style key (`eyJh…`, 552 characters), so it isn't
empty and isn't an old-style anaconda.org token. It still might not be the same
key `ana` has in its keyring. The next test separates "the key is bad" from
"rattler-build sends it the wrong way":

```
K=$(security find-generic-password -s anaconda-api-key -w); for s in token Bearer; do curl -s -o /dev/null -w "$s: %{http_code}\n" -H "Authorization: $s $K" https://api.anaconda.org/user; done
```

- **`token: 401`, `Bearer: 200`:** the key is valid, but anaconda.org only
  accepts it as a Bearer token. rattler-build most likely sends the `token`
  form, which would be a rattler-build bug with the new keys.
- **Both 200:** the key and the auth style are both fine, so the 401 comes from
  somewhere else, such as the key's upload scope or the create-package call. Run
  the upload with `-vvv`.
- **Both 401:** anaconda.org rejects this key. It differs from the one `ana`
  uses.

---

## Prompt 3 (command run)

```
K=$(security find-generic-password -s anaconda-api-key -w); for s in token Bearer; do curl -s -o /dev/null -w "$s: %{http_code}\n" -H "Authorization: $s $K" https://api.anaconda.org/user; done
```

Output:

```
token: 401
Bearer: 401
```

## Response 3

Both requests got 401, so **anaconda.org rejects the key in your Keychain**.
This isn't a rattler-build bug: rattler-build sends that key and gets the same
401 the curl test got.

`ana` works because it authenticates with a different credential, the token it
saved in `~/.anaconda/keyring` when you logged in. The Keychain key is probably
either a different key (expired or revoked), or an anaconda.com account key that
`api.anaconda.org` doesn't accept as a plain token. Either way, don't use it for
uploads.

**Fix: create an anaconda.org upload token and use that.**

1. Create the token, either:
   - in the web UI: anaconda.org → your account (eoas_ubc) → Settings →
     **Access** → create a token with the "Allow write access to the API site"
     scope (`api:write`), or
   - on the command line, with the classic `anaconda-client`:
     ```
     anaconda auth --create --name rattler-upload --scopes 'api:read api:write'
     ```
2. Replace the Keychain item with the new token:
   ```
   security add-generic-password -U -s anaconda-api-key -a "$USER" -w '<new token>'
   ```
3. Check it with the same curl test. It should now return 200:
   ```
   K=$(security find-generic-password -s anaconda-api-key -w); curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: token $K" https://api.anaconda.org/user
   ```
4. Upload (keep `--force`, because 0.3.1 is already on anaconda.org):
   ```
   export ANACONDA_API_KEY=$(security find-generic-password -s anaconda-api-key -w)
   pixi run rattler-build upload anaconda --owner eoas_ubc --force output/noarch/*.conda
   ```
5. Put the same new token in the GitHub repository secret `ANACONDA_API_KEY`, so
   the CI upload job works too.

If the new token passes step 3 but rattler-build still returns 401, run step 4
with `-vvv`.

---

## Prompt 4

```
K=$(security find-generic-password -s anaconda-api-key -w); curl -s -o /dev/null -w "%{http_code}\n" -H "Authorization: token $K" https://api.anaconda.org/user
```

## Response 4

I ran that command and it still returns **401**, so anaconda.org still rejects
the key in the Keychain item `anaconda-api-key`.

If the Keychain item hasn't been replaced with a newly created anaconda.org
token yet, that's expected. Creating the token and running
`security add-generic-password -U …` should fix it.

If it was replaced and still gets 401, check these:

- **The token didn't actually update.** Without `-U`,
  `security add-generic-password` fails when the item already exists. Check the
  first characters:
  ```
  K=$(security find-generic-password -s anaconda-api-key -w); echo "${K:0:4} ${#K}"
  ```
  If it still says `eyJh 552`, it's the old key.
- **Missing scope.** The token needs `api:read` (to fetch `/user`) as well as
  `api:write` (to upload).
- **It was created on anaconda.com rather than anaconda.org.** Account keys from
  anaconda.com look like the old `eyJ…` key and fail the same way. Create the
  token at anaconda.org → Settings → Access.

---

## Prompt 5

> save the prompts and your responses as a markdown file

## Response 5

Saved as `anaconda-upload-session-2026-11-23.md` in the repo root.

---

## Prompt 6

> I'd like to add a small python script to the gen_utils entry points that
> keeps the recipe.yaml version field in sync with the git v* tag

## Response 6

I added a `sync_recipe_version` command to the gen_utils entry points. All 25
tests pass, including 13 new ones. Running `sync_recipe_version --check` in the
repo reports that `recipe/recipe.yaml` (0.3.1) matches `v0.3.1`.

**How it works** (`src/gen_utils/utils/sync_recipe_version.py`):

- It changes only the `version:` line in the recipe's `context:` block.
  Comments, quoting and the rest of the file stay as they are, and
  `package.version: ${{ version }}` is left alone. If the version isn't quoted,
  it adds quotes so a version like `1.10` isn't read as the number 1.1.
- By default it uses the most recent `v*` tag reachable from HEAD and edits
  `recipe/recipe.yaml` at the repo root. `--tag` and `--recipe` override those.
- `--check` changes nothing. It exits 1 if the recipe and tag versions differ,
  and 2 on errors such as no tag or a badly formed tag.

**Order of steps:** a tag points at an existing commit, so set the version
first, then commit, then tag:

```
sync_recipe_version --tag v0.4.0
git commit -am "Set recipe version to 0.4.0"
git tag v0.4.0 && git push origin main v0.4.0
```

Run without `--tag` after tagging, it would change a file the tagged commit
doesn't contain.

**Other changes:**

- `pyproject.toml`: registered the command under `[project.scripts]`.
- `recipe/recipe.yaml`: added the conda entry point, an import test, a `--help`
  test, and a comment on the version line pointing to the tool.
- `tests/test_sync_recipe_version.py`: new tests. The one that needs git is
  skipped when git isn't installed, as may happen in the conda test
  environment.
- `README.md`: a table row and a usage section.

Nothing is committed yet. A small optional addition would be a
`pixi exec sync_recipe_version --check` step in a tag-triggered upload job, so
a release stops if the tag and recipe disagree.

---

## Prompt 7

> will pushing without --tags still trigger the github action?

## Response 7

It depends on what the push contains. The workflow
(`.github/workflows/conda-build.yml`) starts on:

```yaml
on:
  push:
    branches: [main]
    tags: ["v*"]
```

- **`git push` (no tags):** runs if it pushes commits to `main`, but as a
  branch run, not a tag run. Git doesn't push tags unless you ask, so a local
  `v0.4.0` tag stays on your machine, and anything that should happen only for
  a tag won't happen.
- **`git push origin main v0.4.0`:** naming the tag pushes it, so you don't
  need `--tags`. You get two runs, one for the `main` push and one for the
  `v0.4.0` tag push.
- **`git push origin v0.4.0`:** pushes only the tag and starts the tag run.
- **`git push --follow-tags`:** pushes annotated tags only. A plain
  `git tag v0.4.0` creates a lightweight tag, which `--follow-tags` skips. Use
  `git tag -a v0.4.0 -m "0.4.0"` if you want to rely on it.
- **`git push --tags`:** pushes every tag. GitHub doesn't start any workflows
  when one push creates more than three tags.

**The workflow no longer has an upload job.** The current file has just the
`build` job (tests plus `build-conda`); the upload job was removed in commit
`7e299f8` ("remove upload"). So a tag push currently builds and tests on the
three platforms but doesn't upload to anaconda.org. Uploads are done by hand
with `ana org upload` or `rattler-build upload`. The suggested `--check` step
needs somewhere to go, so it waits until an upload job is added back.

---

## Prompt 8

> append this disscussions to today's markdown file

## Response 8

Appended prompts 6–8 and their responses to
`anaconda-upload-session-2026-11-23.md`.
