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
    -   [pytest-mock](https://github.com/pytest-dev/pytest-mock)
-   [pytest configuration](https://docs.pytest.org/en/latest/reference/customize.html) is in _[pyproject.toml](https://github.com/br3ndonland/fastenv/blob/HEAD/pyproject.toml)_.
-   Test coverage reports are generated by [coverage.py](https://github.com/nedbat/coveragepy). To generate test coverage reports, first run tests with `coverage run`, then generate a report with `coverage report`. To see interactive HTML coverage reports, run `coverage html` instead of `coverage report`.

Integration tests will be skipped if cloud credentials are not present. Running integration tests locally will take some additional setup.

#### Make buckets on each supported cloud platform

-   [AWS S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/creating-bucket.html)
-   [Backblaze B2](https://help.backblaze.com/hc/en-us/articles/1260803542610-Creating-a-B2-Bucket-using-the-Web-UI)

#### Upload objects to each bucket

Upload an object to each bucket named `.env.testing`.

The file should have this content:

```sh
# .env
AWS_ACCESS_KEY_ID_EXAMPLE=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY_EXAMPLE=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLE
CSV_VARIABLE=comma,separated,value
EMPTY_VARIABLE=''
# comment
INLINE_COMMENT=no_comment  # inline comment
JSON_EXAMPLE='{"array": [1, 2, 3], "exponent": 2.99e8, "number": 123}'
PASSWORD='64w2Q$!&,,[EXAMPLE'
QUOTES_AND_WHITESPACE='text and spaces'
URI_TO_DIRECTORY='~/dev'
URI_TO_S3_BUCKET=s3://mybucket/.env
URI_TO_SQLITE_DB=sqlite:////path/to/db.sqlite
URL_EXAMPLE=https://start.duckduckgo.com/
OBJECT_STORAGE_VARIABLE='DUDE!!! This variable came from object storage!'
```

#### Generate credentials for each supported cloud platform

There are three sets of credentials needed:

1. AWS temporary credentials
2. AWS static credentials
3. Backblaze static credentials

The [object storage docs](cloud-object-storage.md) have general info on generating the static credentials.

For AWS static credentials, [create a non-admin user](https://docs.aws.amazon.com/IAM/latest/UserGuide/getting-started_create-delegated-user.html). The user will need an [IAM policy](https://docs.aws.amazon.com/IAM/latest/UserGuide/tutorial_managed-policies.html) like the following. This project doesn't do any listing or deleting at this time, so those parts can be omitted if you're going for least privilege.

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": ["s3:ListBucket"],
            "Resource": ["arn:aws:s3:::<AWS_S3_BUCKET_NAME>"]
        },
        {
            "Effect": "Allow",
            "Action": ["s3:PutObject", "s3:GetObject", "s3:DeleteObject"],
            "Resource": ["arn:aws:s3:::<AWS_S3_BUCKET_NAME>/*"]
        }
    ]
}
```

After attaching the IAM policy to the non-admin user, [generate an access key](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html) for the non-admin user, set up an [AWS CLI profile](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-profiles.html) named `fastenv`, and configure it with the access key for the non-admin user. AWS static credentials are now ready.

AWS temporary credentials work a little differently. [Create an IAM role](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_create_for-user.html), with a [resource-based policy](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_identity-vs-resource.html) called a "role trust policy." The role trust policy would look like this (`<AWS_IAM_USERNAME>` is the IAM user that owns the static credentials, not your admin username):

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Principal": {
                "AWS": "arn:aws:iam::<AWS_ACCOUNT_ID>:user/<AWS_IAM_USERNAME>"
            },
            "Action": ["sts:AssumeRole", "sts:TagSession"]
        }
    ]
}
```

Attach the [identity-based policy](https://docs.aws.amazon.com/IAM/latest/UserGuide/tutorial_managed-policies.html) you created for the IAM user to the role as well.

The end result is that the IAM user can assume the IAM role and obtain temporary credentials. The temporary credentials have the same IAM policy as the regular access key, so tests can be [parametrized](https://docs.pytest.org/en/latest/how-to/fixtures.html#parametrizing-fixtures) accordingly.

#### Run all the tests

Once you're finally done with all that, maybe go out for a walk or something.

Then come back, and run these magic words:

```sh
# set the required input variables
AWS_IAM_ROLE_NAME="paste-here"
AWS_S3_BUCKET_HOST="paste-here"
BACKBLAZE_B2_ACCESS_KEY_FASTENV="paste-here"
# leading space to avoid storing secret key in shell history
# set `HISTCONTROL=ignoreboth` for Bash or `setopt histignorespace` for Zsh
 BACKBLAZE_B2_SECRET_KEY_FASTENV="paste-here"
BACKBLAZE_B2_BUCKET_HOST="paste-here"
BACKBLAZE_B2_BUCKET_REGION="paste-here"

# get AWS account ID from STS (replace fx with jq or other JSON parser as needed)
AWS_ACCOUNT_ID=$(aws sts get-caller-identity | fx .Account)

# assume the IAM role to get temporary credentials
ASSUMED_ROLE=$(
  aws sts assume-role \
  --role-arn arn:aws:iam::$AWS_ACCOUNT_ID:role/$AWS_IAM_ROLE_NAME \
  --role-session-name fastenv-testing-local-aws-cli \
  --profile fastenv
)

# run all tests by providing the necessary input variables
AWS_IAM_ACCESS_KEY_FASTENV=$(aws configure get fastenv.aws_access_key_id) \
  AWS_IAM_ACCESS_KEY_SESSION=$(echo $ASSUMED_ROLE | fx .Credentials.AccessKeyId) \
  AWS_IAM_SECRET_KEY_SESSION=$(echo $ASSUMED_ROLE | fx .Credentials.SecretAccessKey) \
  AWS_IAM_SECRET_KEY_FASTENV=$(aws configure get fastenv.aws_secret_access_key) \
  AWS_IAM_SESSION_TOKEN=$(echo $ASSUMED_ROLE | fx .Credentials.SessionToken) \
  AWS_S3_BUCKET_HOST=$AWS_S3_BUCKET_HOST \
  BACKBLAZE_B2_ACCESS_KEY_FASTENV=$BACKBLAZE_B2_ACCESS_KEY_FASTENV \
  BACKBLAZE_B2_SECRET_KEY_FASTENV=$BACKBLAZE_B2_SECRET_KEY_FASTENV \
  BACKBLAZE_B2_BUCKET_HOST=$BACKBLAZE_B2_BUCKET_HOST \
  BACKBLAZE_B2_BUCKET_REGION=$BACKBLAZE_B2_BUCKET_REGION \
  pytest --cov-report=html --durations=0 --durations-min=0.5
```

## GitHub Actions workflows

[GitHub Actions](https://github.com/features/actions) is a continuous integration/continuous deployment (CI/CD) service that runs on GitHub repos. It replaces other services like Travis CI. Actions are grouped into workflows and stored in _.github/workflows_. See [Getting the Gist of GitHub Actions](https://gist.github.com/br3ndonland/f9c753eb27381f97336aa21b8d932be6) for more info.

### GitHub Actions and AWS

#### Static credentials

As explained in the section on [generating credentials for local testing](#generate-credentials-for-each-supported-cloud-platform), a non-admin [IAM user](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_users.html) must be created in order to allow GitHub Actions to access AWS when using [static credentials](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html). The IAM user for this repo was created following [IAM best practices](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html). In AWS, there is a `GitHubActions` IAM group, with a `fastenv` IAM user (one user per repo). The `fastenv` user has an IAM policy attached specifying its permissions.

On GitHub, the `fastenv` user access key is stored in [GitHub Secrets](https://docs.github.com/en/actions/reference/encrypted-secrets).

The bucket host is stored in GitHub Secrets in the "[virtual-hosted-style](https://docs.aws.amazon.com/AmazonS3/latest/userguide/VirtualHosting.html)" format (`<bucketname>.s3.<region>.amazonaws.com`).

#### Temporary credentials

In addition to the static access key, GitHub Actions also retrieves temporary security credentials from AWS using OpenID Connect (OIDC). See the GitHub [docs](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/about-security-hardening-with-openid-connect) for further info.

The OIDC infrastructure is provisioned with Terraform, using a similar approach to the example in [br3ndonland/terraform-examples](https://github.com/br3ndonland/terraform-examples).

### GitHub Actions and Backblaze B2

A [B2 application key](https://www.backblaze.com/b2/docs/application_keys.html) is stored in GitHub Secrets, along with the corresponding bucket host in "virtual-hosted-style" format (`<bucket-name>.s3.<region-name>.backblazeb2.com`).

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
-   **To create a changelog:**

    ```sh
    printf '# Changelog\n\n' >CHANGELOG.md

    GIT_LOG_FORMAT='## %(subject) - %(taggerdate:short)

    %(contents:body)
    Tagger: %(taggername) %(taggeremail)
    Date: %(taggerdate:iso)

    %(contents:signature)'

    git tag -l --sort=-taggerdate:iso --format="$GIT_LOG_FORMAT" >>CHANGELOG.md
    ```
