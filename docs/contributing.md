# Contributing

## Summary

**PRs welcome!**

-   **Consider starting a [discussion](https://github.com/br3ndonland/fastenv/discussions) to see if there's interest in what you want to do.**
-   **Submit PRs from feature branches on forks to the `develop` branch.**
-   **Ensure PRs pass all CI checks.**
-   **Maintain test coverage at 100%.**

## Git

-   _[Why use Git?](https://www.git-scm.com/about)_ Git enables creation of multiple versions of a code repository called branches, with the ability to track and undo changes in detail.
-   Install Git by [downloading](https://www.git-scm.com/downloads) from the website, or with a package manager like [Homebrew](https://brew.sh/).
-   [Configure Git to connect to GitHub with SSH](https://docs.github.com/en/github/authenticating-to-github/connecting-to-github-with-ssh).
-   [Fork](https://docs.github.com/en/get-started/quickstart/fork-a-repo) this repo.
-   Create a [branch](https://www.git-scm.com/book/en/v2/Git-Branching-Branches-in-a-Nutshell) in your fork.
-   Commit your changes with a [properly-formatted Git commit message](https://chris.beams.io/posts/git-commit/).
-   Create a [pull request (PR)](https://docs.github.com/en/github/collaborating-with-pull-requests/proposing-changes-to-your-work-with-pull-requests/about-pull-requests) to incorporate your changes into the upstream project you forked.

## Code quality

### Code style

-   **Python code is formatted with [Black](https://black.readthedocs.io/en/stable/)**. Configuration for Black is stored in _[pyproject.toml](https://github.com/br3ndonland/fastenv/blob/HEAD/pyproject.toml)_.
-   **Python imports are organized automatically with [isort](https://pycqa.github.io/isort/)**.
    -   The isort package organizes imports in three sections:
        1. Standard library
        2. Dependencies
        3. Project
    -   Within each of those groups, `import` statements occur first, then `from` statements, in alphabetical order.
    -   You can run isort from the command line with `poetry run isort .`.
    -   Configuration for isort is stored in _[pyproject.toml](https://github.com/br3ndonland/fastenv/blob/HEAD/pyproject.toml)_.
-   Other web code (JSON, Markdown, YAML) is formatted with [Prettier](https://prettier.io/).

### Static type checking

-   [Mypy](https://mypy.readthedocs.io/en/stable/) is used for type-checking.
-   To learn type annotation basics, see [this gist](https://gist.github.com/987bdc6263217895d4bf03d0a5ff114c) and the [Real Python type checking tutorial](https://realpython.com/python-type-checking/).

### Pre-commit

[Pre-commit](https://pre-commit.com/) runs [Git hooks](https://www.git-scm.com/book/en/v2/Customizing-Git-Git-Hooks). Configuration is stored in _[.pre-commit-config.yaml](https://github.com/br3ndonland/fastenv/blob/HEAD/.pre-commit-config.yaml)_. It can run locally before each commit (hence "pre-commit"), or on different Git events like `pre-push`. Pre-commit is installed in the Poetry environment. To use:

```sh
# after running `poetry install`
path/to/fastenv
❯ poetry shell

# install hooks that run before each commit
path/to/fastenv
.venv ❯ pre-commit install

# and/or install hooks that run before each push
path/to/fastenv
.venv ❯ pre-commit install --hook-type pre-push
```

## Python

### Poetry

This project uses [Poetry](https://python-poetry.org/) for dependency management.

**Install project with all dependencies: `poetry install -E all`**.

#### Highlights

-   **Automatic virtual environment management**: Poetry automatically manages the `virtualenv` for the application.
-   **Automatic dependency management**: rather than having to run `pip freeze > requirements.txt`, Poetry automatically manages the dependency file (called _pyproject.toml_), and enables SemVer-level control over dependencies like [npm](https://semver.npmjs.com/). Poetry also manages a lockfile (called _poetry.lock_), which is similar to _package-lock.json_ for npm. Poetry uses this lockfile to automatically track specific versions and hashes for every dependency.
-   **Dependency resolution**: Poetry will automatically resolve any dependency version conflicts. pip did not have dependency resolution [until the end of 2020](https://pip.pypa.io/en/latest/user_guide/#changes-to-the-pip-dependency-resolver-in-20-3-2020).
-   **Dependency separation**: Poetry can maintain separate lists of dependencies for development and production in the _pyproject.toml_. Production installs can skip development dependencies for speed.
-   **Builds**: Poetry has features for easily building the project into a Python package.

#### Installation

The recommended installation method is through the [Poetry custom installer](https://python-poetry.org/docs/#installation), which vendorizes dependencies into an isolated environment, and allows you to update Poetry with `poetry self update`.

You can also install Poetry however you prefer to install your user Python packages (`pipx install poetry`, `pip install --user poetry`, etc). Use the standard update methods with these tools (`pipx upgrade poetry`, `pip install --user --upgrade poetry`, etc).

#### Key commands

```sh
# Basic usage: https://python-poetry.org/docs/basic-usage/
poetry install  # create virtual environment and install dependencies
poetry show --tree  # list installed packages
poetry add PACKAGE@VERSION # add package production dependencies
poetry add PACKAGE@VERSION --dev # add package to development dependencies
poetry update  # update dependencies (not available with standard tools)
poetry version  # list or update version of this package
poetry shell  # activate the virtual environment, like source venv/bin/activate
poetry run COMMAND  # run a command within the virtual environment
poetry env info  # https://python-poetry.org/docs/managing-environments/
poetry config virtualenvs.in-project true  # install virtualenvs into .venv
poetry export -f requirements.txt > requirements.txt --dev  # export deps
```

### Testing with pytest

-   Tests are in the _tests/_ directory.
-   Run tests by [invoking `pytest` from the command-line](https://docs.pytest.org/en/latest/how-to/usage.html) within the Poetry environment in the root directory of the repo.
-   [pytest](https://docs.pytest.org/en/latest/) features used include:
    -   [fixtures](https://docs.pytest.org/en/latest/how-to/fixtures.html)
    -   [monkeypatch](https://docs.pytest.org/en/latest/how-to/monkeypatch.html)
    -   [parametrize](https://docs.pytest.org/en/latest/how-to/parametrize.html)
    -   [temporary directories and files (`tmp_path`)](https://docs.pytest.org/en/latest/how-to/tmp_path.html)
-   [pytest plugins](https://docs.pytest.org/en/latest/how-to/plugins.html) include:
    -   [pytest-cov](https://github.com/pytest-dev/pytest-cov)
    -   [pytest-mock](https://github.com/pytest-dev/pytest-mock)
-   [pytest configuration](https://docs.pytest.org/en/latest/reference/customize.html) is in _[pyproject.toml](https://github.com/br3ndonland/fastenv/blob/HEAD/pyproject.toml)_.
-   Test coverage results are reported when invoking `pytest` from the command-line. To see interactive HTML coverage reports, invoke pytest with `pytest --cov-report=html`.
-   Test coverage reports are generated within GitHub Actions workflows by [pytest-cov](https://github.com/pytest-dev/pytest-cov) with [coverage.py](https://github.com/nedbat/coveragepy), and uploaded to [Codecov](https://docs.codecov.io/docs) using [codecov/codecov-action](https://github.com/marketplace/actions/codecov). Codecov is then integrated into pull requests with the [Codecov GitHub app](https://github.com/marketplace/codecov).

## GitHub Actions workflows

[GitHub Actions](https://github.com/features/actions) is a continuous integration/continuous deployment (CI/CD) service that runs on GitHub repos. It replaces other services like Travis CI. Actions are grouped into workflows and stored in _.github/workflows_. See [Getting the Gist of GitHub Actions](https://gist.github.com/br3ndonland/f9c753eb27381f97336aa21b8d932be6) for more info.

### GitHub Actions and AWS

An IAM user must be created in order to allow GitHub Actions to access AWS. The IAM user for this repo was created following [IAM best practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html). In AWS, there is a `GitHubActions` IAM group, with a `fastenv` IAM user (one user per repo). The `fastenv` user has an IAM policy attached specifying its permissions.

The AWS CLI was used for setup, with the following [`aws iam` commands](https://awscli.amazonaws.com/v2/documentation/api/latest/reference/iam/index.html):

```sh
~
❯ aws iam create-group --group-name GitHubActions

~
❯ aws iam attach-group-policy --group-name GitHubActions \
  --policy-arn arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess

~
❯ aws iam create-user --user-name fastenv

~
❯ aws iam add-user-to-group --group-name GitHubActions --user-name fastenv

~
❯ aws iam create-access-key --user-name fastenv

```

The S3 bucket itself was created using the AWS CLI, using `aws s3 mb`.

A bucket URL is stored in [GitHub Secrets](https://docs.github.com/en/actions/reference/encrypted-secrets) as `AWS_S3_BUCKET_URL`, in the "[virtual hosted style URL](https://docs.aws.amazon.com/AmazonS3/latest/userguide/VirtualHosting.html)" format (`https://<bucketname>.s3.<region>.amazonaws.com`).

On GitHub, the `fastenv` user access key is stored in GitHub Secrets:

-   `AWS_ACCESS_KEY_ID_FASTENV`
-   `AWS_SECRET_ACCESS_KEY_FASTENV`.

In addition to the static access key, GitHub Actions also retrieves temporary security credentials from AWS using OpenID Connect (OIDC). See the GitHub [changelog](https://github.blog/changelog/2021-10-27-github-actions-secure-cloud-deployments-with-openid-connect/) and [docs](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments) for further info.

### GitHub Actions and Backblaze B2

A [B2 application key](https://www.backblaze.com/b2/docs/application_keys.html) with read and list permissions is stored in [GitHub Secrets](https://docs.github.com/en/actions/reference/encrypted-secrets):

-   `BACKBLAZE_B2_APPLICATION_KEY_ID` (equivalent to `AWS_ACCESS_KEY_ID`)
-   `BACKBLAZE_B2_APPLICATION_KEY` (equivalent to `AWS_SECRET_ACCESS_KEY`)

A bucket URL is stored in GitHub Secrets as `BACKBLAZE_B2_BUCKET_URL`, in the "virtual hosted style URL" format (`https://<bucket-name>.s3.<region-name>.backblazeb2.com`).

See the [Backblaze B2 S3-compatible API docs](https://www.backblaze.com/b2/docs/s3_compatible_api.html) for further info.

## Maintainers

-   **The default branch is `develop`.**
-   **PRs should be merged into `develop`.** Head branches are deleted automatically after PRs are merged.
-   **The only merges to `main` should be fast-forward merges from `develop`.**
-   **Branch protection is enabled on `develop` and `main`.**
    -   `develop`:
        -   Require signed commits
        -   Include administrators
        -   Allow force pushes
    -   `main`:
        -   Require signed commits
        -   Include administrators
        -   Do not allow force pushes
        -   Require status checks to pass before merging (commits must have previously been pushed to `develop` and passed all checks)
-   **To create a release:**
    -   Bump the version number in `pyproject.toml` with `poetry version` and commit the changes to `develop`.
    -   Push to `develop` and verify all CI checks pass.
    -   Fast-forward merge to `main`, push, and verify all CI checks pass.
    -   Create an [annotated and signed Git tag](https://www.git-scm.com/book/en/v2/Git-Basics-Tagging)
        -   Follow [SemVer](https://semver.org/) guidelines when choosing a version number.
        -   List PRs and commits in the tag message:
            ```sh
            git log --pretty=format:"- %s (%h)" \
              "$(git describe --abbrev=0 --tags)"..HEAD
            ```
        -   Omit the leading `v` (use `1.0.0` instead of `v1.0.0`)
        -   Example: `git tag -a -s 1.0.0`
    -   Push the tag. GitHub Actions and Poetry will build the Python package and publish to PyPI.
