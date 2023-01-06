# Changelog

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