# Changelog

## 0.6.0 - 2024-10-05

### Changes

**Drop Python 3.8 support**
(a8a4c59e40481479136411abe7645da3ddaf60b9,
6ca4c1b33736a8648f0d49cf639d66af0fcbaded)

Python 3.8 is at [end-of-life](https://devguide.python.org/versions/).
This release will drop support for Python 3.8. This could be a breaking
change for users still running 3.8, so those users should consider
updating to 3.9 or above.

### Commits

- Bump version from 0.5.0 to 0.6.0 (a6aa08e)
- Upgrade syntax after dropping Python 3.8 (6ca4c1b)
- Drop Python 3.8 support (a8a4c59)
- Update test dependencies for FastAPI 0.115 (9a164e2)
- Update to Ruff 0.6 (d02e241)
- Update to `mypy==1.11.2` (a601145)
- Update to `pipx==1.7.1` (75b589d)
- Update to FastAPI 0.112 (8bc5f5d)
- Don't hard-code repo name in GitHub Actions jobs (6ac42e3)
- Use dedicated GitHub Actions job for PyPI (d0e973c)
- Update to `hatch==1.12.0` (a80ba80)
- Update to `pipx==1.6.0` (025443a)
- Update to `mypy==1.10.1` (6faaadf)
- Update to Ruff 0.5 (816d464)
- Update to Prettier 3 (fc811c5)
- Update to FastAPI 0.111 (984db1f)
- Add project background link to README (34e5b94)
- Add suggested pronounciation to README (4dedbf9)
- Update changelog for version 0.5.0 (#33) (6bb820c)

Tagger: Brendon Smith <bws@bws.bio>

Date: 2024-10-05 14:58:44 -0400

```text
-----BEGIN SSH SIGNATURE-----
U1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAgwLDNmire1DHY/g9GC1rGGr+mrE
kJ3FC96XsyoFKzm6IAAAADZ2l0AAAAAAAAAAZzaGE1MTIAAABTAAAAC3NzaC1lZDI1NTE5
AAAAQPPZQ0NDiNZzqt9et0v3OaudHfusChrIQaFQNVPBQj83va5Iy5H3Vyt0GQ0Er3A6Z4
ScxrGs62HHdwz2Q4gxuAg=
-----END SSH SIGNATURE-----
```

## 0.5.0 - 2024-04-11

### Changes

**Document and test FastAPI integration** (#32, 7362541497bb975cb021552ebf2a0fe9a5cd0a99)

One of the goals of this project as shown in the README is to unify
settings management for FastAPI. It would be helpful to provide a simple
example of how to integrate fastenv with a FastAPI app. The most common
use case for fastenv would be to load environment variables and settings
when the FastAPI app starts up. The recommended way to customize app
startup and shutdown is with lifespan events.

This release will add an example to the quickstart in the README that uses
[lifespan events](https://fastapi.tiangolo.com/advanced/events/) with
[lifespan state](https://www.starlette.io/lifespan/#lifespan-state).
Lifespan state is the recommended way to share objects between the
lifespan function and API endpoints.

Currently, the lifespan function can only have one required argument for
the FastAPI or Starlette app instance. This is because of the way
Starlette runs the lifespan function, as seen in the source code
[here](https://github.com/encode/starlette/blob/4e453ce91940cc7c995e6c728e3fdf341c039056/starlette/routing.py#L732).
This is shown, but not explained, in the
[FastAPI docs on lifespan events](https://fastapi.tiangolo.com/advanced/events/) -
the code examples use objects from outside the lifespan function by
instantiating them at the top-level of the module. Unfortunately this
limits lifespan event customization. For example, an application might
want a way to customize the dotenv file path or the object storage
bucket from which the dotenv file needs to be downloaded. One way to
customize the dotenv file path is to set an environment variable with
the dotenv file path, then pass the environment variable value into
`fastenv.load_dotenv()`. This is demonstrated in the new tests.

The new tests will build on the example in the README by loading a
dotenv file into a FastAPI app instance with `fastenv.load_dotenv()`.
The resultant `DotEnv` instance will then be accessed within an API
endpoint by reading the lifespan state on `request.state`. As explained
in the [Starlette lifespan docs](https://www.starlette.io/lifespan/),
the `TestClient` must be used as a context manager to trigger lifespan.

Thanks to @clabnet for prompting this change in
[br3ndonland/fastenv#28](https://github.com/br3ndonland/fastenv/discussions/28).

**Add support for Python 3.12** (#31, 53464862ffcec4292cbee1407a32a471f43e9da8)

This release will add
[Python 3.12](https://docs.python.org/3/whatsnew/3.12.html)
support to fastenv.

- fastenv will now include a Python 3.12 classifier in its PyPI package
- fastenv will now build and publish its PyPI package using Python 3.12
- fastenv will now run tests with Python 3.12, in addition to 3.8-3.11

### Commits

- Bump version from 0.4.2 to 0.5.0 (26fd927)
- Document and test FastAPI integration (#32) (7362541)
- Update to pytest 8 (1e8b896)
- Update path to contributing.md in PR template (d51c035)
- Update contact info in code of conduct (41bc76c)
- Add support for Python 3.12 (#31) (5346486)
- Update changelog for version 0.4.2 (#30) (ed436f9)

Tagger: Brendon Smith <bws@bws.bio>

Date: 2024-04-11 16:36:09 -0400

```text
-----BEGIN SSH SIGNATURE-----
U1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAgwLDNmire1DHY/g9GC1rGGr+mrE
kJ3FC96XsyoFKzm6IAAAADZ2l0AAAAAAAAAAZzaGE1MTIAAABTAAAAC3NzaC1lZDI1NTE5
AAAAQPKWdrKJ0W0TLNMY/hIRlUxqKZ8zDQkP4cb2z73PtFQe9NuFnTcsfQPhITox4xUves
1jKisa4IV780duz3vJrQA=
-----END SSH SIGNATURE-----
```

## 0.4.2 - 2024-04-09

### Changes

**Avoid auto-inactivating GitHub Actions deployments** (6d6f5c9)

Version 0.4.1 and commit 6e532c6 configured Python package publication
to use PyPI OIDC with GitHub Actions deployment environments.
This commit provides a small update to deployment environment usage.
Each use of a deployment environment creates a deployment that can be
either active or inactive. GitHub Actions auto-inactivates deployments,
and although this behavior is not configurable or documented, there are
some possible workarounds/hacks suggested by a community discussion
[comment](https://github.com/orgs/community/discussions/67982#discussioncomment-7086962).
The workaround used here will be to provide each deployment with its own
unique URL.

### Commits

- Bump version from 0.4.1 to 0.4.2 (ff9d56f)
- Avoid auto-inactivating GitHub Actions deployments (6d6f5c9)
- Reset `peter-evans/create-pull-request@v6` author (845e8b2)
- Update changelog for version 0.4.1 (#29) (b60a73d)

Tagger: Brendon Smith <bws@bws.bio>

Date: 2024-04-09 05:27:45 -0400

```text
-----BEGIN SSH SIGNATURE-----
U1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAgwLDNmire1DHY/g9GC1rGGr+mrE
kJ3FC96XsyoFKzm6IAAAADZ2l0AAAAAAAAAAZzaGE1MTIAAABTAAAAC3NzaC1lZDI1NTE5
AAAAQMWcRBk51C/WrcmVgcm7jLrP82RsbXeLL84Q6AmgYlMQBOzdsMkdi4YI2khtoS7BvE
Go3ymR0RVJiG5DOGZeXAE=
-----END SSH SIGNATURE-----
```

## 0.4.1 - 2024-04-08

### Changes

**Publish to PyPI with OIDC trusted publisher** (6e532c6)

This commit will update Python package publishing to the newest format
recommended by PyPI. This project previously published packages with a
project-scoped PyPI API token (token only valid for this project) stored
in GitHub Secrets and the `hatch publish` command. The project will now
publish packages using a
[PyPI OIDC](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-pypi)
(OpenID Connect) trusted publisher with the
[pypa/gh-action-pypi-publish](https://github.com/pypa/gh-action-pypi-publish)
action. This is the method that Hatch itself uses (pypa/hatch#891)
(Hatch does not "dogfood" its own `hatch publish` feature).

The advantage to OIDC is that authentication is performed with temporary
API tokens (only valid for 15 minutes) instead of persistent tokens that
must be manually generated on PyPI and pasted into GitHub Secrets. The
disadvantage is that authentication is more complicated.

To use PyPI OIDC, a trusted publisher was set up for the PyPI project
as shown in the [PyPI docs](https://docs.pypi.org/trusted-publishers/).
Next, a dedicated
[GitHub Actions deployment environment](https://docs.github.com/en/actions/deployment/targeting-different-environments/using-environments-for-deployment)
was created for PyPI, with protection rules that only allow use of the
environment with workflow runs triggered by Git tags. The environment
protection rules combine with tag protection rules in existing
[GitHub rulesets](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-rulesets/about-rulesets)
to ensure PyPI packages can only be published when a maintainer pushes a
Git tag.

The GitHub Actions workflow will be updated to use the deployment
environment. Deployment environments must be selected at the job level
before the job begins, so a setup job will be added that selects the
appropriate deployment environment and passes it to the PyPI job.
Finally, after `hatch build` outputs the package build files to the
`dist/` directory, pypa/gh-action-pypi-publish will be used to publish
the package to PyPI. The pypa/gh-action-pypi-publish action publishes
exact version tags like pypa/gh-action-pypi-publish@v1.8.14, and offers
Git branches for major and minor version numbers like
pypa/gh-action-pypi-publish@release/v1.8.

### Commits

- Bump version from 0.4.0 to 0.4.1 (d668549)
- Publish to PyPI with OIDC trusted publisher (6e532c6)
- Update to `peter-evans/create-pull-request@v6` (0918b9e)
- Add support for AnyIO 4 (b33e84e)
- Update to Ruff 0.3 (658fb4b)
- Update to `mypy==1.9.0` (64adf48)
- Update to `hatch==1.9.4` (6c60f7e)
- Update to `pipx==1.5.0` (795e1d2)
- Update comparisons docs for Starlette 0.37 (99e233f)
- Disable CodeQL `setup-python-dependencies` (11d8d60)
- Update to Node.js 20 actions (a6d2e06)
- Update changelog for version 0.4.0 (#27) (649cc4c)

Tagger: Brendon Smith <bws@bws.bio>

Date: 2024-04-08 18:47:35 -0400

```text
-----BEGIN SSH SIGNATURE-----
U1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAgwLDNmire1DHY/g9GC1rGGr+mrE
kJ3FC96XsyoFKzm6IAAAADZ2l0AAAAAAAAAAZzaGE1MTIAAABTAAAAC3NzaC1lZDI1NTE5
AAAAQFcFuhsLNWl82ozsEevXNRMuBeJQ9VhpBZdSz5Luxu5iNO33VApk9/PFhHW8mxR1lR
/ukfFvXg6jXOgunBq6Qwg=
-----END SSH SIGNATURE-----
```

## 0.4.0 - 2024-01-29

### Changes

**Add support for Cloudflare R2 object storage** (#26, 6b06299)

The fastenv object storage client supports AWS S3 and Backblaze B2.
This release will add support for the
[Cloudflare R2](https://developers.cloudflare.com/r2/)
object storage platform. Cloudflare R2 buckets can be supplied as
"virtual-hosted-style" URLs, like
`<BUCKET>.<ACCOUNT_ID>.r2.cloudflarestorage.com`.

**Add PUT uploads to object storage client** (#25, 6968353)

Dotenv files are commonly kept in cloud object storage. fastenv provides
an object storage client for downloading and uploading dotenv files.

S3-compatible object storage allows uploads with either `POST` or `PUT`.
This release will add an implementation of uploads with `PUT`, and `PUT`
will now be the default because `PUT` uploads are more widely-supported
and standardized. Backblaze B2 does not currently support single-part
uploads with `POST` to their S3 API (the
[B2 native API](https://www.backblaze.com/apidocs/b2-upload-file) must
be used instead).
[Cloudflare R2](https://developers.cloudflare.com/r2/api/s3/presigned-urls/)
does not support uploads with `POST` at all.

**Use Ruff for linting and formatting** (e635c33)

[Ruff](https://docs.astral.sh/ruff/) is a Python linter and formatter
that has gained popularity due to its high performance and numerous
capabilities. Now that Ruff has released its
[first minor version series](https://astral.sh/blog/ruff-v0.1.0) (0.1)
and has a [versioning policy](https://docs.astral.sh/ruff/versioning/),
it's a good time to consider adopting it.

As of this release, the project's Python linting and formatting checks
will be migrated from the previous tools (Black, Flake8, isort) to Ruff.

### Commits

- Bump version from 0.3.0 to 0.4.0 (620af5e)
- Add support for Cloudflare R2 object storage (#26) (6b06299)
- Add PUT uploads to object storage client (#25) (6968353)
- Remove trailing slash from `bucket_host` (8492656)
- Update test info in CONTRIBUTING.md (69bdf05)
- Update to `peter-evans/create-pull-request@v5` (4ddb5b5)
- Update to `aws-actions/configure-aws-credentials@v4` (e59316e)
- Update to `actions/checkout@v4` (ebdea31)
- Update CodeQL workflow actions (03e80cc)
- Address CodeQL URL substring sanitization error (a822a86)
- Remove scheme from `bucket_host` (aaf3f1d)
- Remove curly quote (0f2c1bb)
- Use Ruff for linting and formatting (e635c33)
- Add wheel build target to avoid Hatch `ValueError` (a7fffb7)
- Update to `pipx==1.4.1` (a53eb2b)
- Update to `mypy==1.8.0` (16c6329)
- Update to `hatch==1.9.1` (2ab4bff)
- Update to `pipx==1.4.0` (31c9854)
- Update to `pipx==1.3.3` (f5ddd6d)
- Remove unneeded stale workflow (d86b4ba)
- Switch from pre-commit to Hatch scripts (0f60779)
- Finish configuring code block copy (34fbe9a)
- Add docs deployment info to contributing.md (70b358e)
- Remove Material for MkDocs version from README (380f364)
- Configure Material for MkDocs code block copy (5c8b6ea)
- Update to Material for MkDocs 9 (a1349d4)
- Relax upper bound on HTTPX (ab0e909)
- Update to `mypy==1.7.0` (27549f5)
- Prepend `$HATCH_ENV` in GitHub Actions workflow (c5cf02d)
- Update to `hatch==1.7.0` (d8ee4e6)
- Remove Sourcery configuration file (9f61678)
- Update Black in pre-commit (6fd48d6)
- Update to `mypy==1.3.0` (e1a0e09)
- Update to coverage 7 (8702743)
- Update to `pipx==1.2.0` (dcbe73b)
- Update to mypy 1.1.1 (f666fdb)
- Update to configure-aws-credentials@v2 (5d20126)
- Update changelog for version 0.3.0 (#23) (d13a924)

Tagger: Brendon Smith <bws@bws.bio>

Date: 2024-01-29 18:44:39 -0500

```text
-----BEGIN SSH SIGNATURE-----
U1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAgwLDNmire1DHY/g9GC1rGGr+mrE
kJ3FC96XsyoFKzm6IAAAADZ2l0AAAAAAAAAAZzaGE1MTIAAABTAAAAC3NzaC1lZDI1NTE5
AAAAQJ5iKQerDHiHWEGliUGY/CsOZ8MNoHxG3j4LPio1G+CeF29pNv/WLzWPRmaEbR3p8N
ORKJgY1v1TfHUEHmpW2w4=
-----END SSH SIGNATURE-----
```

## 0.3.0 - 2023-02-26

### Changes

**Add Python 3.11 support** (#15)

This release will add
[Python 3.11](https://docs.python.org/3/whatsnew/3.11.html)
support to fastenv.

- fastenv will now include a Python 3.11 classifier in its PyPI package
- fastenv will now build and publish its PyPI package using Python 3.11
- fastenv will now run tests with Python 3.11, in addition to 3.8-3.10

**Migrate from Poetry 1.1 to Hatch** (#14, f0c6882, 78755e7, e2f8d04, 85b8e79, 903a7de)

fastenv has been migrated to [Hatch](https://hatch.pypa.io/latest/).
See br3ndonland/inboard#56 for more details and context around the
motivations for this.

The Python package version will now be available at `fastenv.__version__`.

**Auto-generate changelog from Git tags** (c7aa765)

A changelog will now be provided at
[CHANGELOG.md](https://github.com/br3ndonland/fastenv/blob/develop/CHANGELOG.md)
for viewing on GitHub, and
[in the docs at the `/changelog` endpoint](https://fastenv.bws.bio/changelog).

**Enable mypy strict mode** (7fbb89f)

Mypy will run in strict mode on all Python code (source code and tests).
In terms of user-facing improvements, this update will add a new module
`fastenv.types` for cloud object storage upload policy types.

The contributing.md will be updated with instructions for type checking.

### Commits

`0.2.5..0.3.0`

- Bump version from 0.3.0-beta.0 to 0.3.0 (2864bee)
- Update to mypy 1 (4df9eac)
- Update to Black 23 (bccad2c)
- Update isort to avoid poetry-core breaking change (e417e07)
- Update changelog for version 0.3.0-beta.0 (#22) (f6f2ce9)
- Bump version from 0.3.0-alpha.0 to 0.3.0-beta.0 (cc56f8d)
- Fix upper bound on HTTPX optional dependency (903a7de)
- Alphabetize Hatch commands in contributing.md (85b8e79)
- Regroup testing info in contributing.md (e2f8d04)
- Remove PEP 631 references from README (4f1e57c)
- Add trailing comma to `pyproject.toml` classifiers (78755e7)
- Alphabetize fields in `pyproject.toml` (f0c6882)
- Update changelog for version 0.3.0-alpha.0 (#16) (69487f9)
- Bump version from 0.2.5 to 0.3.0-alpha.0 (f83b3e0)
- Add Python 3.11 support (#15) (0fcbc5f)
- Remove unused `.prettierrc` (6d2c8c3)
- Merge pull request #14 from br3ndonland/hatch (801e256)
- Update docs for Hatch (3e7e049)
- Update GitHub Actions workflows for Hatch (e5fb5d6)
- Update configuration files for Hatch (5d409be)
- Add spell check with CSpell (e2df8c0)
- Auto-generate changelog from Git tags (c7aa765)
- Enable mypy strict mode (7fbb89f)
- Update pre-commit dependencies (8324d2c)
- Update dependencies (2d0793c)

Tagger: Brendon Smith <bws@bws.bio>

Date: 2023-02-26 13:04:53 -0500

```text
-----BEGIN SSH SIGNATURE-----
U1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAgwLDNmire1DHY/g9GC1rGGr+mrE
kJ3FC96XsyoFKzm6IAAAADZ2l0AAAAAAAAAAZzaGE1MTIAAABTAAAAC3NzaC1lZDI1NTE5
AAAAQPmQOgANjAFVhHDndp2Nap9CY+b/kOLbx/mX0JKs1dirCj9BLfT/R8qxJtquy66pi5
MZwfvpny7olFG4Kn6/rwQ=
-----END SSH SIGNATURE-----
```

## 0.3.0-beta.0 - 2023-01-16

### Changes

**Add Python 3.11 support** (#15)

This release will add
[Python 3.11](https://docs.python.org/3/whatsnew/3.11.html)
support to fastenv.

- fastenv will now include a Python 3.11 classifier in its PyPI package
- fastenv will now build and publish its PyPI package using Python 3.11
- fastenv will now run tests with Python 3.11, in addition to 3.8-3.10

**Migrate from Poetry 1.1 to Hatch** (#14, f0c6882, 78755e7, e2f8d04, 85b8e79, 903a7de)

fastenv has been migrated to [Hatch](https://hatch.pypa.io/latest/).
See br3ndonland/inboard#56 for more details and context around the
motivations for this.

The Python package version will now be available at `fastenv.__version__`.

**Auto-generate changelog from Git tags** (c7aa765)

A changelog will now be provided at
[CHANGELOG.md](https://github.com/br3ndonland/fastenv/blob/develop/CHANGELOG.md)
for viewing on GitHub, and
[in the docs at the `/changelog` endpoint](https://fastenv.bws.bio/changelog).

**Enable mypy strict mode** (7fbb89f)

Mypy will run in strict mode on all Python code (source code and tests).
In terms of user-facing improvements, this update will add a new module
`fastenv.types` for cloud object storage upload policy types.

The contributing.md will be updated with instructions for type checking.

### Commits

- Bump version from 0.3.0-alpha.0 to 0.3.0-beta.0 (cc56f8d)
- Fix upper bound on HTTPX optional dependency (903a7de)
- Alphabetize Hatch commands in contributing.md (85b8e79)
- Regroup testing info in contributing.md (e2f8d04)
- Remove PEP 631 references from README (4f1e57c)
- Add trailing comma to `pyproject.toml` classifiers (78755e7)
- Alphabetize fields in `pyproject.toml` (f0c6882)
- Update changelog for version 0.3.0-alpha.0 (#16) (69487f9)
- Bump version from 0.2.5 to 0.3.0-alpha.0 (f83b3e0)
- Add Python 3.11 support (#15) (0fcbc5f)
- Remove unused `.prettierrc` (6d2c8c3)
- Merge pull request #14 from br3ndonland/hatch (801e256)
- Update docs for Hatch (3e7e049)
- Update GitHub Actions workflows for Hatch (e5fb5d6)
- Update configuration files for Hatch (5d409be)
- Add spell check with CSpell (e2df8c0)
- Auto-generate changelog from Git tags (c7aa765)
- Enable mypy strict mode (7fbb89f)
- Update pre-commit dependencies (8324d2c)
- Update dependencies (2d0793c)

Tagger: Brendon Smith <bws@bws.bio>

Date: 2023-01-16 17:09:08 -0500

```text
-----BEGIN SSH SIGNATURE-----
U1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAgwLDNmire1DHY/g9GC1rGGr+mrE
kJ3FC96XsyoFKzm6IAAAADZ2l0AAAAAAAAAAZzaGE1MTIAAABTAAAAC3NzaC1lZDI1NTE5
AAAAQL+UiOjWdlfmjSqfE5t/SxVZkk/8Q3yPqquBtPvgMK5x5jE1TC09h8SrMU/s8ogx3R
uKBw4nhahHEl/oqou26gg=
-----END SSH SIGNATURE-----
```

## 0.3.0-alpha.0 - 2023-01-05

Changes:

**Add Python 3.11 support** (#15)

This release will add
[Python 3.11](https://docs.python.org/3/whatsnew/3.11.html)
support to fastenv.

- fastenv will now include a Python 3.11 classifier in its PyPI package
- fastenv will now build and publish its PyPI package using Python 3.11
- fastenv will now run tests with Python 3.11, in addition to 3.8-3.10

**Migrate from Poetry 1.1 to Hatch** (#14)

fastenv has been migrated to [Hatch](https://hatch.pypa.io/latest/).
See br3ndonland/inboard#56 for more details and context around the
motivations for this.

The Python package version will now be available at `fastenv.__version__`.

**Auto-generate changelog from Git tags** (c7aa765)

A changelog will now be provided at
[CHANGELOG.md](https://github.com/br3ndonland/fastenv/blob/develop/CHANGELOG.md)
for viewing on GitHub, and
[in the docs at the `/changelog` endpoint](https://fastenv.bws.bio/changelog).

**Enable mypy strict mode** (7fbb89f)

Mypy will run in strict mode on all Python code (source code and tests).
In terms of user-facing improvements, this update will add a new module
`fastenv.types` for cloud object storage upload policy types.

The contributing.md will be updated with instructions for type checking.

Commits:

- Bump version from 0.2.5 to 0.3.0-alpha.0 (f83b3e0)
- Add Python 3.11 support (#15) (0fcbc5f)
- Remove unused `.prettierrc` (6d2c8c3)
- Merge pull request #14 from br3ndonland/hatch (801e256)
- Update docs for Hatch (3e7e049)
- Update GitHub Actions workflows for Hatch (e5fb5d6)
- Update configuration files for Hatch (5d409be)
- Add spell check with CSpell (e2df8c0)
- Auto-generate changelog from Git tags (c7aa765)
- Enable mypy strict mode (7fbb89f)
- Update pre-commit dependencies (8324d2c)
- Update dependencies (2d0793c)

Tagger: Brendon Smith <bws@bws.bio>

Date: 2023-01-05 21:34:04 -0500

```text
-----BEGIN SSH SIGNATURE-----
U1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAgwLDNmire1DHY/g9GC1rGGr+mrE
kJ3FC96XsyoFKzm6IAAAADZ2l0AAAAAAAAAAZzaGE1MTIAAABTAAAAC3NzaC1lZDI1NTE5
AAAAQLxzSE0qq+dNRJKqfdL41qz5Cp4xHW7TNABnxD5bp+Vl0IW+p3XUW85dESWWOMIvo+
0oLqAAWYluKl2fO5oa/w0=
-----END SSH SIGNATURE-----
```

## 0.2.5 - 2022-11-26

Commits:

- Bump version from 0.2.4 to 0.2.5 (92bc9dc)
- Update to Flake8 6 (23503a5)
- Update type annotations for PEP 484 (20eb205)
- Update dependencies (8e99ff4)

Note about Git commit and tag verification:

The email address bws@bws.bio and associated GPG key 783DBAF23C1D6478
have been used to sign Git commits and tags since 0.1.0 - 2021-07-27.

Git and GitHub now support commit signing and verification with SSH. The
SSH key fingerprint SHA256:w+KL3qQKtku1MfLFSZLCl93kSgxH3O4OvtcxHG5k0Go
will also be used to sign Git commits and tags going forward.

See https://github.com/br3ndonland and br3ndonland/br3ndonland@08257e6
for corroboration of the new info.

Tagger: Brendon Smith <bws@bws.bio>

Date: 2022-11-26 16:45:08 -0500

```text
-----BEGIN SSH SIGNATURE-----
U1NIU0lHAAAAAQAAADMAAAALc3NoLWVkMjU1MTkAAAAgwLDNmire1DHY/g9GC1rGGr+mrE
kJ3FC96XsyoFKzm6IAAAADZ2l0AAAAAAAAAAZzaGE1MTIAAABTAAAAC3NzaC1lZDI1NTE5
AAAAQFxR6tNPUG7uc5eDWEUY50ErKsPYJcB4MseB3gISrHw/ymXlrLXFgfW1XRSq4dqivm
tgrbY2MHDvnvzKKsfJyAw=
-----END SSH SIGNATURE-----
```

## 0.2.4 - 2022-09-04

Commits:

- Bump version from 0.2.3 to 0.2.4 (e7b5814)
- Update to Flake8 5 (6250255)
- Update dependencies (2c0267c)
- Add changelog command to docs (8162c83)

Tagger: Brendon Smith <bws@bws.bio>

Date: 2022-09-04 14:15:08 -0400

```text
-----BEGIN PGP SIGNATURE-----

iHUEABYKAB0WIQRUOcb2PA6NDBflNNd4PbryPB1keAUCYxTrNQAKCRB4PbryPB1k
eNc5AQC5ZKIPUkKcKpjOLK+Y9Q5sezqL9+FVyF1bWr9VysGOAgEA52hc028InxLd
EKdvP0VjjRFvVezFpNmThiDTa9z1hAA=
=jYCh
-----END PGP SIGNATURE-----
```

## 0.2.3 - 2022-06-11

Commits:

- Bump version from 0.2.2 to 0.2.3 (42af2d0)
- Update stale workflow (d8eedbd)
- Update to pipx 1.1.0 (0ca9a9e)
- Update dependencies (2ec067b)

Tagger: Brendon Smith <bws@bws.bio>

Date: 2022-06-11 15:24:57 -0400

```text
-----BEGIN PGP SIGNATURE-----

iHUEABYKAB0WIQRUOcb2PA6NDBflNNd4PbryPB1keAUCYqTsFQAKCRB4PbryPB1k
eLSVAP0TQ5TaJzkBPd0dgOTACF9CiiTNcXQmJFubX1xjU5KUVQD/awI5Gn5L1wap
KasWTLD5GOcLWjvHy7HtSppeRunF/AI=
=KHgo
-----END PGP SIGNATURE-----
```

## 0.2.2 - 2022-05-28

Commits:

- Bump version from 0.2.1 to 0.2.2 (0fddd80)
- Update to HTTPX 0.23 (fb4fa0b)
- Update dependencies (b6b6e59)
- Update CodeQL workflow actions (bf9d0da)
- Merge pull request #12 from br3ndonland/drop-codecov (dde5d74)
- Specify source files for coverage.py (fca4234)
- Fix inadvertent pytest fixture session token usage (5532293)
- Run pytest with coverage.py in GitHub Actions (962458c)
- Raise coverage of tests to 100% (82a7866)
- Remove pytest-cov and just use coverage.py (fd29a0f)
- Remove Codecov upload from GitHub Actions workflow (8b464e6)
- Add shields.io badge for test coverage (df03d14)
- Remove Codecov badge from README (e832aa5)
- Remove Codecov YAML (a834fac)

Tagger: Brendon Smith <bws@bws.bio>

Date: 2022-05-28 14:52:28 -0400

```text
-----BEGIN PGP SIGNATURE-----

iHUEABYKAB0WIQRUOcb2PA6NDBflNNd4PbryPB1keAUCYpJvpAAKCRB4PbryPB1k
eNrdAQCspNDN0vpQhSCb4AjiV4DpLsq8Yh5cFN0kpCsLhVRpbgEAt7VjXtG4IL0S
Ts+q5rlpFkY31bXe/Ck5IfILoclC4QY=
=8CX8
-----END PGP SIGNATURE-----
```

## 0.2.1 - 2022-04-11

Changes:

Enforce presigned URL min and max expiration times (6c75a76)

Commits:

- Bump version from 0.2.0 to 0.2.1 (ef91d53)
- Update to v3 actions (b546cb6)
- Enforce presigned URL min and max expiration times (6c75a76)
- Add Sourcery config file to set Python version (a0f0a34)
- Update dependencies (c947c21)
- Update to codecov/codecov-action@v3 (99b2b65)

Tagger: Brendon Smith <bws@bws.bio>

Date: 2022-04-11 17:54:55 -0400

```text
-----BEGIN PGP SIGNATURE-----

iHUEABYKAB0WIQRUOcb2PA6NDBflNNd4PbryPB1keAUCYlSkFgAKCRB4PbryPB1k
eDBXAP9auyDwwS2VODgUGR0RbS6I5CYay9Lh6RGy/YvlOIIX6gEA7XRY3TlAvsNT
w+8ZuwG/HzjjVq/cOfYfrs9MTDhkWgk=
=Ed6h
-----END PGP SIGNATURE-----
```

## 0.2.0 - 2022-04-09

Changes:

Integrate with object storage (#8)

Commits:

- Bump version from 0.1.4 to 0.2.0 (f752d31)
- Update to pytest 7 (4a76b69)
- Update dependencies (be473b7)
- Merge pull request #8 from br3ndonland/object-storage (b06add0)
- Remove extra Material for MkDocs annotations (9e349e8)
- Address CodeQL URL substring sanitization error (6156a2d)
- Refactor #8 with Sourcery (#9) (a34b9be)
- Move object storage code to `fastenv.cloud` (8d70777)
- Implement object storage client directly (835801d)
- Update Black to resolve pre-commit `ImportError` (a63fe07)
- Remove `aioaws` from dependencies (ca9a39f)
- Integrate with object storage using `aioaws` (7bfbd8f)
- Add `aioaws` to dependencies (2bb9514)
- Add quickstart section to README (2574865)
- Update to Material for MkDocs 8 (334b793)
- Update dependencies (f2b10d5)
- Simplify `DotEnv._sort_dotenv` comprehension (24664e6)
- Add default filename to `load_dotenv` docs (a956e44)
- Update dependencies (74f0209)
- Add missing token permissions to CodeQL workflow (319cd50)

Tagger: Brendon Smith <bws@bws.bio>

Date: 2022-04-09 18:34:56 -0400

```text
-----BEGIN PGP SIGNATURE-----

iHUEABYKAB0WIQRUOcb2PA6NDBflNNd4PbryPB1keAUCYlIKPwAKCRB4PbryPB1k
eG+0AQDpam+9RUO47+5po7EQPjPvKPVi1ghaPzA2loOj066BiQD/eGhZR9dGAjoc
NgjHVX6BV0uAMrE7MBByNq2MuFjY0gg=
=xcZb
-----END PGP SIGNATURE-----
```

## 0.1.4 - 2021-11-09

- Bump version from 0.1.3 to 0.1.4 (8302177)
- Refactor test data into parametrized fixtures (044be0a)
- Remove remaining uses of `example_dict` from tests (9d9b0d7)
- Allow deletion of empty variables from `DotEnv`s (cb728f9)
- Organize repetitive assertion into helper method (9e74aa3)
- Use `items()` to directly unpack dictionary values (41990df)
- Update dependencies (f334af9)
- Test package version before publishing to PyPI (935f081)
- Test Poetry virtualenv location (67c375b)
- Disable Poetry experimental new installer (bd58436)
- Add push triggers back to CodeQL workflow (861f16e)

Tagger: Brendon Smith <bws@bws.bio>

Date: 2021-11-09 17:41:55 -0500

```text
-----BEGIN PGP SIGNATURE-----

iHUEABYKAB0WIQRUOcb2PA6NDBflNNd4PbryPB1keAUCYYr5SAAKCRB4PbryPB1k
eGlyAPkBRftCYGpfY2NMw40sH6oyQeVDG5WOVlhYl4AQwiNj1QEAmcoM/6L5+++m
9Nvyc7MtZDcLOHgXvy5VpVg3rpJlXgc=
=M4jL
-----END PGP SIGNATURE-----
```

## 0.1.3 - 2021-10-23

- Bump version from 0.1.2 to 0.1.3 (4489b5d)
- Update dependencies (15e35a0)
- Merge pull request #7 from br3ndonland/python-3.10 (2ea05a4)
  Add Python 3.10 support
- Add Python 3.10 to GitHub Actions workflow (1a2e46b)
- Merge pull request #6 from br3ndonland/poetry-version (b9d417b)
  Pin and test Poetry version
- Pin and test Poetry version (ed7c8d2)
- Update Codecov YAML Boolean syntax (47065f8)
- Rename AWS credentials in docs and tests (908dfcf)
- Add PEP 621 and PEP 631 links to docs (de08de9)
- Clarify limitations of `os.environ` in comparisons (c1c8605)
- Update dependencies (b55defb)
- Remove `find_dotenv(starting_dir)` docs reference (753f529)
- Update dependencies (a16595d)
- Disable Git LFS for images for Vercel deployment (cbeab06)
- Use heroicons cog as favicon (80878b7)
- Add missing MkDocs favicon config (b60a4b5)

Tagger: Brendon Smith <bws@bws.bio>

Date: 2021-10-23 17:32:38 -0400

```text
-----BEGIN PGP SIGNATURE-----

iHUEABYKAB0WIQRUOcb2PA6NDBflNNd4PbryPB1keAUCYXSAAAAKCRB4PbryPB1k
eE0oAQCtjzZ/h8ZtGrJV8lKHrRAThgsd9fWAt8zhb4ovegUEmgD5Ab6kkH6527C+
35sItU2XI2Pa+0dpbmODlxZUIWCDvAU=
=SSjv
-----END PGP SIGNATURE-----
```

## 0.1.2 - 2021-08-06

- Bump version from 0.1.1 to 0.1.2 (8b3115c)
- Update dependencies (87706d6)
- Implement `DotEnv` sorting (0f77ee3)
- Test `find_dotenv` on resolved paths and filenames (aec7672)
- Clean up `load_dotenv` tests (043626a)
- Add missing `test_` prefix to `dump_dotenv` test (dea4ef4)

Tagger: Brendon Smith <bws@bws.bio>

Date: 2021-08-06 13:38:27 -0400

```text
-----BEGIN PGP SIGNATURE-----

iHUEABYKAB0WIQRUOcb2PA6NDBflNNd4PbryPB1keAUCYQ1zogAKCRB4PbryPB1k
eDp6AP4m4+Ru6WJZE3ZUR0y384SJv6ArRlGLARh6TR7z1kFTZgEAkDRch0H9nba3
EwTBNJ5M8YyedUU6tHHFEUUKPycqsgY=
=UcsZ
-----END PGP SIGNATURE-----
```

## 0.1.1 - 2021-08-01

- Bump version from 0.1.0 to 0.1.1 (597590f)
- Update dependencies (c5dbdaf)
- Merge pull request #5 from br3ndonland/load_dotenv_multi (796e10c)
  Load multiple .env files with `load_dotenv`
- Refactor `load_dotenv` into smaller methods (74ca273)
- Organize repetitive assertions with helper methods (b1c8c72)
- Add missing `from __future__ import annotations` (83b7696)
- Document how to load multiple .env files (07cfa3b)
- Load multiple .env files with `load_dotenv` (0813a5e)
- Simplify `venv` code blocks in docs (400cb3e)
- Drop "Development Status" PyPI trove classifier (a5188d1)
- Correct `find_dotenv` docstring typo (d42fd15)

Tagger: Brendon Smith <bws@bws.bio>

Date: 2021-08-01 19:49:51 -0400

```text
-----BEGIN PGP SIGNATURE-----

iHUEABYKAB0WIQRUOcb2PA6NDBflNNd4PbryPB1keAUCYQczaAAKCRB4PbryPB1k
eL86AP0cDuyvxVMIgXTSaTHL2bMT2klzvgX22R/Jz3+bbrPtSAEAnYnUR6uw9i5N
84unqsXm21vgqxbFtoIAx46lfdEFxQs=
=v0/5
-----END PGP SIGNATURE-----
```

## 0.1.0 - 2021-07-27

This release will enable fastenv to manage environment variables and
.env files, completing two of the five project aims. Of particular note,
fastenv could be considered a suitable replacement for python-dotenv,
addressing its many limitations.

Special thanks to AnyIO for providing useful utilities that power this
project, especially the pytest plugin and the new `anyio.Path` class
released in version 3.3.0.

- Bump version from 0.0.1 to 0.1.0 (99f7e29)
- Update dependencies (f920539)
- Update to codecov-action@v2 and new uploader (046571c)
- Move CONTRIBUTING.md to docs (01ac280)
- Merge pull request #2 from br3ndonland/dotenv (ab10ad6)
  Enable fastenv to manage environment variables and .env files
- Update project aims after implementing dotenv code (72c9c89)
- Use `anyio.Path` for asynchronous path operations (9eb8dc4)
- Require AnyIO (609d968)
- Remove AnyIO file I/O `# type: ignore[arg-type]` (347da2a)
- Update to `anyio@'^3.3'` (742543d)
- Add logging to `find_dotenv` and `load_dotenv` (5f28508)
- Implement async file I/O with AnyIO (9164f98)
- Implement `DotEnv` class for environment variables (512b36d)
- Add AnyIO to dependencies (efd1815)
- Add "documentation" field to pyproject.toml (ef9ba4c)
- Add "repository" field to pyproject.toml (690de61)
- Update repo tagline (dc09595)
- Improve grammar and content of comparisons docs (cebf58a)
- Use checkboxes for project aims (0df5e74)
- Clarify object storage aim in README and docs (ea00c95)
- Remove `site_url` and trailing slash from docs (5497278)
- Merge pull request #1 from br3ndonland/docs (3662c98)
  Add documentation
- Add docs comparing fastenv with other projects (05836f1)
- Add placeholder for environment variable docs (940dcb5)
- Add favicon from Material for MkDocs (f6346ac)
- Update docs homepage with info from README (e669e13)
- Configure MkDocs site (02fb162)
- Create MkDocs site (69d2bd5)
- Add dependencies for docs (ea1f49c)
- Update Poetry installs for install-poetry.py (6521198)
- Run CI on Python 3.8 and 3.9 (f982106)
- Set minimum Python version to 3.8 (924c9be)
- Update dependencies (e376c5f)
- Update to Black 21.6b0 (2e45be2)
- Update dependencies (b5ad374)
- Update to mypy 0.9x (7676ef6)
- Update author info in pyproject.toml (47833fe)
- Update mypy configuration file (5472439)
- Update dependencies (2328d41)
- Update flake8 pre-commit hook for new GitHub repo (4912bfe)
- Update to Black 21.5b2 (098fdcc)
- Add classifiers and keywords to pyproject.toml (ed0b13d)
- Add PyPI badge to README (d3d54fb)
- Add Codecov badge to README (31c4b9b)

Tagger: Brendon Smith <bws@bws.bio>

Date: 2021-07-27 02:02:25 -0400

```text
-----BEGIN PGP SIGNATURE-----

iHUEABYKAB0WIQRUOcb2PA6NDBflNNd4PbryPB1keAUCYP+igAAKCRB4PbryPB1k
eLejAQCvTVT+PqTjLcw8oVArebBIWXSB8S1ElSsTU1IkIE1ZTQD+KR4Z/AWnPD9N
tioLAzehNCXR9mjr4wRi4hvfTfs1aAU=
=mBFU
-----END PGP SIGNATURE-----
```

## 0.0.1 - 2021-04-04

Hello, World! A new project is born. Let's see how this goes!

Tagger: Brendon Smith <br3ndonland@protonmail.com>

Date: 2021-04-04 03:21:05 -0400

```text
-----BEGIN PGP SIGNATURE-----

iQIzBAABCAAdFiEE8JoyBFTTcRFWvTCPrGY4TPqMabAFAmBpaQkACgkQrGY4TPqM
abAYUQ/+PaqJLmEFE0D8fc+TobIL+KswqI/EWCjFr7rxcAGWArQVQyXWZpVF32lD
kiQO1yuxvNzwH5BZ5iQ8MiwnUpnpFdHeLFc/PPcWjmMLVUF4bCVEX3gnHjs7uu5g
K+ia6OvDMRNKKOSfSjDYzRRWRvT1GvLuf+ZIIx62T/t961W0bgPVpKCoqwmS3X9e
tIBqmqQFJB6u/jIHiBTVooUdCj4apXa+nseEl+YuUtlvFCmYhq8/1SY9s+UyKF3+
2w/8H2r+JPv61aVhxakc9hJNRkHKlv6eNUAjVd8Nq8o44KJzplDt7tRTKwdRaudh
MyXNGNpgRkN7iwOKUgE7gH7xyOl2gfF2mo3KtIz7rvw/oY8KH6PSKHNsmIHUS+yn
DaPuZ5+t5gkzQUqrz7caJZwXcSR3bXx3SbzkQkanmVVaP0wlSNFa/BgRqWOYW1KC
NtSVCiyaN6BJ3wY0hQzXLhRd3XI2naCgL2yqZrSY+WeLMN3ApD88y1qjv0XVqoHm
dnuIvdTrYftCXZp4IB72AkEGhnDFLQ7dEdQDWnsWbtgMo6Mg13QFZWNJv5/SNyWO
ozYKX8tkh1CF5Oguv8L+vTSPh03hPxBghNScSxLmfOr5yrPm/jhN0aUqvfvpAGBX
HMlyIRnWW2Z2q6Zlo4iENC+9PVSBsAx2ioM99mfAGmkIlB1O9AA=
=9bDg
-----END PGP SIGNATURE-----
```
