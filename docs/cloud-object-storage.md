# Cloud object storage

## Overview

Dotenv files are commonly kept in [cloud object storage](https://en.wikipedia.org/wiki/Cloud_storage), but environment variable management packages typically don't integrate with object storage clients. Additional logic is therefore required to download the files from object storage prior to loading environment variables. This project offers integration with S3-compatible object storage. [AWS S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html) and [Backblaze B2](https://www.backblaze.com/b2/docs/) are directly supported and tested.

!!!info "Object storage client"

    fastenv uses [aioaws](https://github.com/samuelcolvin/aioaws) as its object storage client. _Why use aioaws instead of [Boto3](https://github.com/boto/boto3)?_

    -   **Async**. aioaws and fastenv use [HTTPX](https://github.com/encode/httpx) for asynchronous HTTP operations. Boto3's methods use synchronous I/O.
    -   **Simple**. aioaws and fastenv are small, simple projects that provide the necessary features without the bloat of Boto3. Why install all of Boto3 if you just need a few of the features?
    -   **Type-annotated**. aioaws and fastenv are fully type-annotated. Boto3 is not type-annotated. Its objects are created at runtime using factory methods, making the code difficult to annotate and read. Some attempts are being made to add type annotations (see [alliefitter/boto3_type_annotations](https://github.com/alliefitter/boto3_type_annotations), [boto/botostubs](https://github.com/boto/botostubs), [vemel/mypy_boto3_builder](https://github.com/vemel/mypy_boto3_builder), and [vemel/boto3-ide](https://github.com/vemel/boto3-ide)), but these attempts are still works-in-progress.

## Getting started

### Set up a virtual environment

To get started, let's set up a virtual environment and install fastenv from the command line. If you've been through the [environment variable docs](environment.md#getting-started), the only change here is installing the optional extras with `python -m pip install fastenv[cloud]` or `python -m pip install fastenv[all]`.

!!!example "Setting up a virtual environment"

    ```sh
    python3 -m venv .venv
    . .venv/bin/activate
    python -m pip install fastenv[cloud]
    ```

### Save a _.env_ file

We'll work with an example _.env_ file that contains variables in various formats. Copy the code block below using the "Copy to clipboard" icon in the top right of the code block, paste the contents into a new file in your text editor, and save it as `.env`.

!!!example "Example .env file"

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

    ```

These environment variables are formatted as described in the [environment variable docs](environment.md#tips).

### Create a bucket

We'll also need to create a bucket in cloud object storage. Backblaze B2 offers 10 GB for free, so consider [signing up](https://www.backblaze.com/b2/sign-up.html) and [creating a bucket](https://help.backblaze.com/hc/en-us/articles/1260803542610-Creating-a-B2-Bucket-using-the-Web-UI) there.

You can also [create a bucket on AWS S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/creating-bucket.html) if you prefer.

### Create credentials

Credentials are usually required in order to connect to an object storage bucket.

Credentials for cloud object storage have two parts: a non-secret portion and a secret portion.

Backblaze calls these credentials "[application keys](https://www.backblaze.com/b2/docs/application_keys.html)."

AWS calls these credentials "[access keys](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html)," and commonly stores them in environment variables named `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and optionally `AWS_SESSION_TOKEN`. Access keys can be [retreived programmatically with the AWS CLI](https://awscli.amazonaws.com/v2/documentation/api/latest/reference/configure/index.html) to avoid saving values in the shell history.

!!!example "Retrieving AWS access keys programmatically with the AWS CLI"

    ```sh
    AWS_ACCESS_KEY_ID=$(aws configure get fastenv.aws_access_key_id)
    AWS_SECRET_ACCESS_KEY=$(aws configure get fastenv.aws_secret_access_key)
    ```

## Uploading files

Now that we have a bucket, let's upload the _.env_ file to the bucket. It's a three step process:

1. **Create a configuration instance**.
2. **Create a client instance**.
3. **Use the client's upload method to upload the file**. To upload, we need to specify a source, and a destination **key**. A key is like a file path. AWS uses the term "[key](https://docs.aws.amazon.com/general/latest/gr/glos-chap.html#K)" because buckets don't have actual directories. The "file path" inside the bucket is just a virtual path, not a concrete file path.

Here's an example of how the code might look:

!!!example "Uploading a _.env_ file to a bucket"

    ```py
    #!/usr/bin/env python3
    # example.py
    from __future__ import annotations

    import anyio
    import fastenv
    import httpx


    async def upload_my_dotenv(
        aws_s3_bucket: str,
        aws_region: str,
        bucket_key: str = "uploads/fastenv-docs/.env",
        source: anyio.Path | str = ".env",
    ) -> httpx.Response | None:
        cloud_config = fastenv.cloud.S3Config(  # (1)
            aws_s3_bucket=aws_s3_bucket,
            aws_region=aws_region,
        )
        cloud_client = fastenv.cloud.S3Client(config=cloud_config)  # (2)
        return await cloud_client.upload(key=bucket_key, source=source)  # (3)


    if __name__ == "__main__":
        aws_s3_bucket = "<YOUR_BUCKET_NAME_HERE>"
        aws_region = "<YOUR_BUCKET_REGION_HERE>"
        anyio.run(upload_my_dotenv, aws_s3_bucket, aws_region)

    ```

    1. Step 1: create a configuration instance
    2. Step 2: create a client instance
    3. Step 3: use the client's upload method to upload the file

## Downloading files

We now have a bucket with a _.env_ file in it. Let's download the file. Steps are pretty much the same.

!!!example "Downloading a _.env_ file from a bucket"

    ```py
    #!/usr/bin/env python3
    # example.py
    from __future__ import annotations

    import anyio
    import fastenv
    import httpx


    async def upload_my_dotenv(
        aws_s3_bucket: str,
        aws_region: str,
        bucket_key: str = "uploads/fastenv-docs/.env",
        source: anyio.Path | str = ".env",
    ) -> httpx.Response | None:
        cloud_config = fastenv.cloud.S3Config(  # (1)
            aws_s3_bucket=aws_s3_bucket,
            aws_region=aws_region,
        )
        cloud_client = fastenv.cloud.S3Client(config=cloud_config)  # (2)
        return await cloud_client.upload(key=bucket_key, source=source)  # (3)


    async def download_my_dotenv(
        aws_s3_bucket: str,
        aws_region: str,
        bucket_key: str = "uploads/fastenv-docs/.env",
        destination: anyio.Path | str = ".env.download",
    ) -> anyio.Path:
        cloud_config = fastenv.cloud.S3Config(
            aws_s3_bucket=aws_s3_bucket,
            aws_region=aws_region,
        )
        cloud_client = fastenv.cloud.S3Client(config=cloud_config)
        return await cloud_client.download(key=bucket_key, destination=destination)


    if __name__ == "__main__":
        aws_s3_bucket = "<YOUR_BUCKET_NAME_HERE>"
        aws_region = "<YOUR_BUCKET_REGION_HERE>"
        # anyio.run(upload_my_dotenv, aws_s3_bucket, aws_region)
        anyio.run(download_my_dotenv, aws_s3_bucket, aws_region)

    ```

## Cloud platform object storage comparisons

### AWS S3

-   Pricing
    -   See the [Backblaze B2 pricing page](https://www.backblaze.com/b2/cloud-storage-pricing.html) for comparisons
    -   See [Backblaze Blog 2021-12-03: Why the world needs lower egress fees](https://www.backblaze.com/blog/why-the-world-needs-lower-egress-fees/) and [Cloudflare Blog 2021-07-23: AWS's egregious egress](https://blog.cloudflare.com/aws-egregious-egress/) for criticisms
-   Identity and Access Management (IAM):
    -   [AWS IAM in S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-access-control.html)
    -   [AWS Signature Version 4](https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-auth-using-authorization-header.html)
-   URIs:
    -   Path style URL: `https://s3.<region>.amazonaws.com/<bucketname>/<keyname>`. _Deprecated (see the [AWS blog](https://aws.amazon.com/blogs/aws/amazon-s3-path-deprecation-plan-the-rest-of-the-story/))_.
    -   [Virtual hosted style URL](https://docs.aws.amazon.com/AmazonS3/latest/userguide/VirtualHosting.html): `https://<bucketname>.s3.<region>.amazonaws.com/<keyname>`. _This is the recommended URL format_.
    -   S3 URI: `s3://<bucketname>/<keyname>`. _This method is only used for certain AWS tools like the AWS CLI (see [docs](https://awscli.amazonaws.com/v2/documentation/api/latest/reference/s3/index.html) and [source code](https://github.com/aws/aws-cli/blob/fa4b05b4bad8574441e4d969aa1ad58a30ff550d/awscli/customizations/s3/utils.py#L217-L250))_.
    -   [Presigned URLs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/ShareObjectPreSignedURL.html)
-   [Bucket naming rules](https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingBucket.html):

    > An Amazon S3 bucket name is globally unique, and the namespace is shared by all AWS accounts. This means that after a bucket is created, the name of that bucket cannot be used by another AWS account in any AWS Region until the bucket is deleted.

### Azure Blob Storage

[Azure Blob Storage](https://docs.microsoft.com/en-us/azure/storage/blobs/storage-blobs-overview) is not S3-compatible, and will not be directly supported by fastenv. In downstream projects that store _.env_ file objects in Azure, users are welcome to download objects using the [Azure Python SDK](https://docs.microsoft.com/en-us/azure/storage/blobs/storage-quickstart-blobs-python), and then load the files with `fastenv.load_dotenv()` after download.

### Backblaze B2

-   [Pricing](https://www.backblaze.com/b2/cloud-storage-pricing.html):
    -   Data storage fees are 1/3 the price of S3
    -   Outbound (also called download or egress) data transfer fees are 1/4 the price of S3
    -   See [Backblaze Blog 2021-12-03: Why the world needs lower egress fees](https://www.backblaze.com/blog/why-the-world-needs-lower-egress-fees/)
-   [S3-compatible API](https://www.backblaze.com/b2/docs/s3_compatible_api.html)\*
    -   Downloading and listing operations are S3-compatible
    -   \*Uploads are different, though there are [good reasons](https://www.backblaze.com/blog/design-thinking-b2-apis-the-hidden-costs-of-s3-compatibility/) for that (helps Backblaze keep pricing low)
-   URIs:
    -   Path style URL: `https://s3.<region>.backblazeb2.com/<bucketname>`
    -   Virtual hosted style URL: `https://<bucketname>.s3.<region>.backblazeb2.com`
    -   Presigned URLs are supported
-   Identity and Access Management (IAM):
    -   Simpler than AWS, while also providing fine-grained access controls.
    -   No configuration of IAM users or roles needed. Access controls are configured on the access keys themselves.
    -   Account master access key is separate from bucket access keys
    -   Access key permissions can be scoped to individual buckets, and even object names within buckets.
-   Docs
    -   [Backblaze B2 docs: Application keys](https://www.backblaze.com/b2/docs/application_keys.html)
    -   [Backblaze B2 docs: S3-compatible API](https://www.backblaze.com/b2/docs/s3_compatible_api.html)

### Cloudflare R2

_Coming soon!_

-   [Cloudflare Blog 2021-07-23: AWS's egregious egress](https://blog.cloudflare.com/aws-egregious-egress/)
-   [Cloudflare Blog 2021-09-28: Announcing Cloudflare R2 Storage](https://blog.cloudflare.com/introducing-r2-object-storage/)

### DigitalOcean Spaces

-   Pricing: $5 monthly flat rate
    -   Up to 250GB of data storage
    -   No charge for inbound data transfer
    -   Up to 1TB of outbound data transfer (also called download or egress)
-   [S3-compatible API](https://docs.digitalocean.com/reference/api/spaces-api/)
-   URIs:
    -   Path style URL: `https://<region>.digitaloceanspaces.com/<bucketname>`
    -   Virtual hosted style URL: `https://<bucketname>.<region>.digitaloceanspaces.com`
    -   Presigned URLs are supported
-   Identity and Access Management (IAM):
    -   Minimal (access keys automatically access all buckets/"spaces")
    -   Access keys can be created without paying the monthly fee
-   Docs
    -   [DigitalOcean docs: Spaces](https://docs.digitalocean.com/products/spaces/)
    -   [DigitalOcean docs: Spaces - Using DigitalOcean Spaces with AWS S3 SDKs](https://docs.digitalocean.com/products/spaces/resources/s3-sdk-examples/)
    -   [DigitalOcean docs: Spaces - How-Tos - Manage access to Spaces](https://docs.digitalocean.com/products/spaces/how-to/manage-access/)

### Google Cloud Storage

-   [Pricing](https://cloud.google.com/storage/pricing) (see the [Backblaze B2 pricing page](https://www.backblaze.com/b2/cloud-storage-pricing.html) for comparisons)
-   [S3-compatible API? Mostly?](https://cloud.google.com/storage/docs/migrating)
-   URIs:
    -   Path style URL: `https://storage.googleapis.com/storage/v1/b/<bucketname>/o/<objectname>`
    -   Virtual hosted style URLs?
    -   [Presigned URLs are supported](https://cloud.google.com/storage/docs/access-control/signed-urls)
-   [Identity and Access Management (IAM)](https://cloud.google.com/storage/docs/access-control/iam)
-   [Docs](https://cloud.google.com/storage/docs)

### Linode Object Storage

-   Pricing: $5 monthly flat rate (same as DigitalOcean Spaces)
    -   250GB of data storage included in the flat rate
    -   No charge for inbound data transfer
    -   Up to 1TB of outbound data transfer (also called download or egress)
    -   Up to 50 Million objects per cluster
-   S3-compatible API
-   URIs:
    -   Path style URL: `https://<region>.linodeobjects.com/<bucketname>`
    -   Virtual hosted style URL: `https://<bucketname>.<region>.linodeobjects.com`
    -   Presigned URLs are supported
-   Identity and Access Management (IAM):
    -   Minimal (access keys automatically access all buckets)
    -   Access keys cannot be created without paying the monthly fee first
-   Docs
    -   [Linode docs: Storage - Object Storage - Overview](https://www.linode.com/docs/products/storage/object-storage/)
    -   [Linode docs: Storage - Object Storage - Guides - Using the AWS SDK for Python (boto3) with Object Storage](https://www.linode.com/docs/products/storage/object-storage/guides/aws-sdk-for-python/)
