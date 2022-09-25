# Cloud object storage

## Overview

Dotenv files are commonly kept in [cloud object storage](https://en.wikipedia.org/wiki/Cloud_storage), but environment variable management packages typically don't integrate with object storage clients. Additional logic is therefore required to download the files from object storage prior to loading environment variables. This project offers integration with S3-compatible object storage. [AWS S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/Welcome.html), [Backblaze B2](https://www.backblaze.com/b2/docs/), and [Cloudflare R2](https://developers.cloudflare.com/r2/) are directly supported and tested.

!!!note "Why not Boto3?"

    fastenv uses its own object storage client. _Why implement a client here instead of using [Boto3](https://github.com/boto/boto3)?_

    -   **Async**. fastenv uses [HTTPX](https://github.com/encode/httpx) for asynchronous HTTP operations. Boto3's methods use synchronous I/O.
    -   **Simple**. fastenv is a small, simple project that provides the necessary features without the bloat of Boto3. Why install all of Boto3 if you just need a few of the features? And if you actually want to understand what your code is doing, you can try sifting through Boto's subpackages and dynamically-generated objects, but wouldn't you rather just look at a few hundred lines of code right in front of you?
    -   **Type-annotated**. fastenv is fully type-annotated. Boto3 is not type-annotated. Its objects are dynamically generated at runtime using factory methods, making the code difficult to annotate and read. Some attempts are being made to add type annotations (see [alliefitter/boto3_type_annotations](https://github.com/alliefitter/boto3_type_annotations), [boto/botostubs](https://github.com/boto/botostubs), [vemel/mypy_boto3_builder](https://github.com/vemel/mypy_boto3_builder), and [vemel/boto3-ide](https://github.com/vemel/boto3-ide)), but these attempts are still works-in-progress.

???info "Building an object storage client from scratch"

    ### Configuration

    fastenv provides a configuration class to manage credentials and other information related to cloud object storage buckets.

    - Buckets can be specified in "[virtual-hosted-style](https://docs.aws.amazon.com/AmazonS3/latest/userguide/VirtualHosting.html)", like `<BUCKET_NAME>.s3.<REGION>.amazonaws.com` for AWS S3 or `<BUCKET_NAME>.s3.<REGION>.backblazeb2.com` for Backblaze B2.
    - If credentials are not provided as arguments, this class will auto-detect configuration from the default AWS environment variables `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_SESSION_TOKEN`, and the region from either `AWS_S3_REGION`, `AWS_REGION`, or `AWS_DEFAULT_REGION`, in that order.
    - [Boto3 detects credentials from several other locations](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html), including credential files and instance metadata endpoints. These other locations are not currently supported.

    ### AWS Signature Version 4

    [AWS Signature Version 4](https://docs.aws.amazon.com/general/latest/gr/signature-version-4.html) is the secret sauce that allows requests to flow through AWS services. fastenv uses its own implementation of AWS Signature Version 4 to connect to AWS S3 and other S3-compatible platforms like Backblaze B2.

    Creating a signature is a [four-step process](https://docs.aws.amazon.com/general/latest/gr/sigv4_signing.html):

    1. _[Create a canonical request](https://docs.aws.amazon.com/IAM/latest/UserGuide/create-signed-request.html)_. "Canonical" just means that the string has a standard set of fields. These fields provide request metadata like the HTTP method and headers.
    2. _[Create a string to sign](https://docs.aws.amazon.com/general/latest/gr/sigv4-create-string-to-sign.html)_. In this step, a SHA256 hash of the canonical request is calculated, and combined with some additional authentication information to produce a new string called the "string to sign." The Python standard library package [`hashlib`](https://docs.python.org/3/library/hashlib.html) makes this straightforward.
    3. _[Calculate a signature](https://docs.aws.amazon.com/general/latest/gr/sigv4-calculate-signature.html)_. To set up this step, a signing key is derived with successive rounds of HMAC hashing. The [concept behind HMAC](https://www.okta.com/identity-101/hmac/) ("Keyed-Hashing for Message Authentication" or "Hash-based Message Authentication Codes") is to generate hashes with mostly non-secret information, along with a small amount of secret information that both the sender and recipient have agreed upon ahead of time. The secret information here is the secret access key. The signature is then calculated with another round of HMAC, using the signing key and the string to sign. The Python standard library package [`hmac`](https://docs.python.org/3/library/hmac.html) does most of the hard work here.
    4. _[Add the signature to the HTTP request](https://docs.aws.amazon.com/general/latest/gr/sigv4-add-signature-to-request.html)_. The hex digest of the signature is included with the request.

    ### Object storage operations

    Once the AWS Signature Version 4 process is in place, it can be used to authorize object storage operations. There are three categories of operations: download, upload, and list.

    #### Download

    The download method generates a presigned URL, uses it to download file contents, and either saves the contents to a file or returns the contents as a string.

    Downloads with `GET` can be authenticated by including AWS Signature Version 4 information either with [request headers](https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-auth-using-authorization-header.html) or [query parameters](https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-query-string-auth.html). fastenv uses query parameters to generate [presigned URLs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/using-presigned-url.html). The advantage to presigned URLs with query parameters is that URLs can be used on their own.

    A related operation is [`head_object`](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/s3.html#S3.Client.head_object), which can be used to check if an object exists. The request is the same as a `GET`, except the [`HEAD` HTTP request method](https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods/HEAD) is used. fastenv does not provide an implementation of `head_object` at this time, but it could be considered in the future.

    #### Upload

    The upload method uploads source contents to an object storage bucket, selecting the appropriate upload strategy based on the cloud platform being used. Uploads can be done with either `POST` or `PUT`.

    [Uploads with `PUT` can use presigned URLs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/PresignedUrlUploadObject.html). Unlike downloads with `GET`, presigned `PUT` URL query parameters do not necessarily contain all the required information. Additional information may need to be supplied in request headers. In addition to supplying header keys and values with HTTP requests, header keys should be signed into the URL in the `X-Amz-SignedHeaders` query string parameter. These request headers can specify:

    -   [Object encryption](https://docs.aws.amazon.com/AmazonS3/latest/userguide/serv-side-encryption.html). Encryption information can be specified with headers including `X-Amz-Server-Side-Encryption`. Note that, although similar headers like `X-Amz-Algorithm` are included as query string parameters in presigned URLs, `X-Amz-Server-Side-Encryption` is not. If `X-Amz-Server-Side-Encryption` is included in query string parameters, it may be silently ignored by the object storage platform. [AWS S3 now automatically encrypts all objects](https://docs.aws.amazon.com/AmazonS3/latest/userguide/default-encryption-faq.html) and [Cloudflare R2 does also](https://docs.aws.amazon.com/AmazonS3/latest/userguide/default-encryption-faq.html), but [Backblaze B2 will only automatically encrypt objects if the bucket has default encryption enabled](https://www.backblaze.com/docs/cloud-storage-server-side-encryption).
    -   [Object metadata](https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingMetadata.html). Headers like `Content-Disposition`, `Content-Length`, and `Content-Type` can be supplied in request headers.
    -   [Object integrity checks](https://docs.aws.amazon.com/AmazonS3/latest/userguide/checking-object-integrity.html). The `Content-MD5` header, defined by [RFC 1864](https://www.rfc-editor.org/rfc/rfc1864), can supply a base64-encoded MD5 checksum. After the upload is completed, the object storage platform server will calculate a checksum for the object in the same manner. If the client and server checksums are the same, this means that all expected information was successfully sent to the server. If the checksums are different, this may mean that object information was lost in transit, and an error will be reported. Note that, although Backblaze B2 accepts and processes the `Content-MD5` header, it will report a SHA1 checksum to align with [uploads to the B2-native API](https://www.backblaze.com/docs/en/cloud-storage-file-information).

    [Uploads with `POST`](https://docs.aws.amazon.com/AmazonS3/latest/API/sigv4-UsingHTTPPOST.html) work differently than `GET` or `PUT` operations. A typical back-end engineer might ask, "Can't I just `POST` binary data to an API endpoint with a bearer token or something?" To which AWS might respond, "No, not really. Here's how you do it instead: pretend like you're submitting a web form." "What?"

    Anyway, here's how it works:

    1. _Create a `POST` policy_. A `POST` policy is a security policy with a list of conditions under which uploads are allowed. It is used instead of the "canonical request" that would be used in query string auth.
    2. _Create a string to sign_. The list is dumped to a string, encoded to bytes in UTF-8 format, Base64 encoded, and then decoded again to a string.
    3. _Calculate a signature_. This step is basically the same as for query string auth. A signing key is derived with HMAC, and then used with the string to sign for another round of HMAC to calculate the signature.
    4. _Add the signature to the HTTP request_. For `POST` uploads, the signature is provided with other required information as form data, rather than as URL query parameters. An advantage of this approach is that it can also be used for browser-based uploads, because the form data can be used to populate the fields of an HTML web form. There is some overlap between items in the `POST` policy and fields in the form data, but they are not exactly the same.

    Backblaze uploads with `POST` are different, though there are [good reasons](https://www.backblaze.com/blog/design-thinking-b2-apis-the-hidden-costs-of-s3-compatibility/) for that (helps keep costs low). fastenv includes an implementation of the Backblaze B2 `POST` upload process.

    #### List

    fastenv does not currently have methods for listing bucket contents.

    Perhaps someone who is willing to spend their free time parsing XML can implement this.

## Getting started

### Set up a virtual environment

To get started, let's set up a virtual environment and install fastenv from the command line. If you've been through the [environment variable docs](environment.md#getting-started), the only change here is installing the optional extras like `python -m pip install fastenv[httpx]`.

!!!example "Setting up a virtual environment"

    ```sh
    python3 -m venv .venv
    . .venv/bin/activate
    python -m pip install fastenv[httpx]
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

We'll also need to create a bucket in cloud object storage. Backblaze B2 and AWS S3 are directly supported and tested.

Backblaze B2 offers 10 GB for free, so consider [signing up](https://www.backblaze.com/b2/sign-up.html) and [creating a bucket](https://help.backblaze.com/hc/en-us/articles/1260803542610-Creating-a-B2-Bucket-using-the-Web-UI) there.

You can also [create a bucket on AWS S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/creating-bucket.html) if you prefer.

### Create credentials

Credentials are usually required in order to connect to an object storage bucket.

Credentials for cloud object storage have two parts: a non-secret portion and a secret portion.

#### AWS

AWS calls these credentials "[access keys](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_access-keys.html)," and commonly stores them in environment variables named `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and optionally `AWS_SESSION_TOKEN`. After [configuring the AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/cli-configure-files.html), access keys can be [retrieved programmatically](https://awscli.amazonaws.com/v2/documentation/api/latest/reference/configure/index.html).

!!!example "Retrieving AWS access keys programmatically with the AWS CLI"

    ```sh
    AWS_ACCESS_KEY_ID=$(aws configure get fastenv.aws_access_key_id)
    AWS_SECRET_ACCESS_KEY=$(aws configure get fastenv.aws_secret_access_key)
    ```

???info "AWS session token support"

    AWS session tokens are used when resources obtain temporary security credentials. The authorization flow works like this:

    -   [IAM roles](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_roles_terms-and-concepts.html), such as [service-linked roles](https://docs.aws.amazon.com/IAM/latest/UserGuide/using-service-linked-roles.html) or [Lambda execution roles](https://docs.aws.amazon.com/lambda/latest/dg/lambda-intro-execution-role.html), are set up and linked to infrastructure resources. These roles can have [two kinds of IAM policies attached](https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_identity-vs-resource.html):
        1.   _Resource-based policies_ called "role trust policies" define how the role can be assumed.
        2.   _Identity-based policies_ define what the role can do once it has been assumed (interactions with other resources on AWS).
    -   The AWS runtime (Fargate, Lambda, etc) requests authorization to use the role by calling the [STS `AssumeRole` API](https://docs.aws.amazon.com/STS/latest/APIReference/API_AssumeRole.html).
    -   If the requesting entity has permissions to assume the role, STS responds with [temporary security credentials](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_temp.html) that have permissions based on the identity-based policies associated with the IAM role.
    -   The AWS runtime stores the temporary security credentials, typically by setting environment variables:
        -   `AWS_ACCESS_KEY_ID`
        -   `AWS_SECRET_ACCESS_KEY`
        -   `AWS_SESSION_TOKEN`
    -   [AWS API calls with temporary credentials](https://docs.aws.amazon.com/IAM/latest/UserGuide/id_credentials_temp_use-resources.html) must include the session token.
    -   The AWS runtime will typically rotate the temporary security credentials before they expire.

    fastenv supports session tokens. The `session_token` argument can be passed to `fastenv.ObjectStorageConfig` or `fastenv.ObjectStorageClient`. If the session token is not provided as an argument, fastenv will check for the environment variable `AWS_SESSION_TOKEN`.

    It is important to keep session token expiration in mind. fastenv will not automatically rotate tokens. Developers are responsible for updating client attributes or instantiating new clients when temporary credentials expire. This is particularly important to keep in mind when generating S3 presigned URLs. As explained in the [docs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/ShareObjectPreSignedURL.html), "If you created a presigned URL using a temporary token, then the URL expires when the token expires, even if the URL was created with a later expiration time."

#### Backblaze

Backblaze calls these credentials "[application keys](https://www.backblaze.com/b2/docs/application_keys.html)." Backblaze doesn't specify environment variable names, so it's easiest to use the same environment variable names as for AWS.

!!!example "Setting Backblaze credentials using AWS variable names"

    ```sh
    AWS_ACCESS_KEY_ID="<YOUR_BACKBLAZE_B2_ACCESS_KEY_HERE>"
    AWS_SECRET_ACCESS_KEY="<YOUR_BACKBLAZE_B2_SECRET_KEY_HERE>"
    ```

!!!tip "Omitting credentials from shell history"

    It's preferable to avoid storing sensitive credentials like `AWS_SECRET_ACCESS_KEY` in your shell history. Thankfully, most shells offer the ability to omit commands from the shell history by prefixing the command with one or more spaces. In Bash, this behavior can be enabled with the [`HISTCONTROL` and `HISTIGNORE`](https://www.gnu.org/software/bash/manual/html_node/Bash-History-Facilities.html) environment variables. In Zsh, this behavior can be enabled with [`HIST_IGNORE_SPACE` or `setopt histignorespace`](https://zsh.sourceforge.io/Doc/Release/Options.html).

## Uploading files

Now that we have a bucket, let's upload the _.env_ file to the bucket. It's a three step process:

1. **Create a configuration instance**. To instantiate `fastenv.ObjectStorageConfig`, provide a bucket and a region. Buckets can be specified with the `bucket_host` argument in "[virtual-hosted-style](https://docs.aws.amazon.com/AmazonS3/latest/userguide/VirtualHosting.html)," like `<BUCKET_NAME>.s3.<REGION>.amazonaws.com` for AWS S3 or `<BUCKET_NAME>.s3.<REGION>.backblazeb2.com` for Backblaze B2. For AWS S3 only, the bucket can be also provided with the `bucket_name` argument as just `<BUCKET_NAME>`. If credentials are not provided as arguments, `fastenv.ObjectStorageConfig` will auto-detect configuration from the default AWS environment variables `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, and `AWS_SESSION_TOKEN`, and the region from either `AWS_S3_REGION`, `AWS_REGION`, or `AWS_DEFAULT_REGION`, in that order. [Boto3 detects credentials](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/credentials.html) from several other locations, including credential files and instance metadata endpoints. These other locations are not currently supported.
2. **Create a client instance**. `fastenv.ObjectStorageClient` instances have two attributes: an instance of `fastenv.ObjectStorageConfig`, and an instance of [`httpx.AsyncClient`](https://www.python-httpx.org/advanced/). They can be automatically instantiated if not provided as arguments. We've instantiated the `fastenv.ObjectStorageConfig` instance separately in step 1 to see how it works, but we'll let `fastenv.ObjectStorageClient` instantiate its `httpx.AsyncClient` automatically. As a shortcut, you could skip step 1 and just provide the configuration arguments to `fastenv.ObjectStorageClient`, like `fastenv.ObjectStorageClient(bucket_host="<BUCKET_NAME>.s3.<REGION>.backblazeb2.com", bucket_region="<REGION>")`.
3. **Use the client's upload method to upload the file**. To upload, we need to specify a source, and a destination path. The destination path is like a file path. AWS uses the term "[key](https://docs.aws.amazon.com/general/latest/gr/glos-chap.html#K)" for these bucket paths because buckets don't have actual directories. The "file path" inside the bucket is just a virtual path, not a concrete file path.

Here's an example of how the code might look. Save the code snippet below as _example.py_.

!!!example "Uploading a _.env_ file to a bucket"

    ```py
    #!/usr/bin/env python3
    # example.py
    from __future__ import annotations

    import anyio
    import fastenv
    import httpx


    async def upload_my_dotenv(
        bucket_host: str,
        bucket_region: str,
        bucket_path: str = "uploads/fastenv-docs/.env",
        source: anyio.Path | str = ".env",
    ) -> httpx.Response | None:
        config = fastenv.ObjectStorageConfig(  # (1)
            bucket_host=bucket_host,
            bucket_region=bucket_region,
        )
        client = fastenv.ObjectStorageClient(config=config)  # (2)
        return await client.upload(bucket_path, source)  # (3)


    if __name__ == "__main__":
        bucket_host = "<BUCKET_NAME>.s3.<REGION>.backblazeb2.com"
        bucket_region = "<REGION>"
        anyio.run(upload_my_dotenv, bucket_host, bucket_region)

    ```

    1. Step 1: create a configuration instance
    2. Step 2: create a client instance
    3. Step 3: use the client's upload method to upload the file

    Then set credentials and run the script from a shell. Remember to activate the virtualenv if you haven't already done so.

    ```sh
    AWS_ACCESS_KEY_ID="<YOUR_ACCESS_KEY_HERE>" \
      AWS_SECRET_ACCESS_KEY="<YOUR_SECRET_KEY_HERE>" \
      python example.py
    ```

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
        bucket_host: str,
        bucket_region: str,
        bucket_path: str = "uploads/fastenv-docs/.env",
        source: anyio.Path | str = ".env",
    ) -> httpx.Response | None:
        config = fastenv.ObjectStorageConfig(
            bucket_host=bucket_host,
            bucket_region=bucket_region,
        )
        client = fastenv.ObjectStorageClient(config=config)
        return await client.upload(bucket_path, source)


    async def download_my_dotenv(
        bucket_host: str,
        bucket_region: str,
        bucket_path: str = "uploads/fastenv-docs/.env",
        destination: anyio.Path | str = ".env.download",
    ) -> anyio.Path:
        config = fastenv.ObjectStorageConfig(
            bucket_host=bucket_host,
            bucket_region=bucket_region,
        )
        client = fastenv.ObjectStorageClient(config=config)
        return await client.download(bucket_path, destination)


    if __name__ == "__main__":
        bucket_host = "<BUCKET_NAME>.s3.<REGION>.backblazeb2.com"
        bucket_region = "<REGION>"
        # anyio.run(upload_my_dotenv, bucket_host, bucket_region)
        anyio.run(download_my_dotenv, bucket_host, bucket_region)

    ```

    Then set credentials and run the script from a shell. Remember to activate the virtualenv if you haven't already done so.

    ```sh
    AWS_ACCESS_KEY_ID="<YOUR_ACCESS_KEY_HERE>" \
      AWS_SECRET_ACCESS_KEY="<YOUR_SECRET_KEY_HERE>" \
      python example.py
    ```

## Downloading multiple files

Sometimes applications use multiple _.env_ files. For example, a team may have a common _.env_ file that provides variables used across many applications. Each application may also have its own _.env_ file to customize, or add to, the variables in the common file.

Here's an example of how this could be implemented.

!!!example "Downloading multiple _.env_ files"

    ```py
    #!/usr/bin/env python3
    # example.py
    from __future__ import annotations

    import anyio
    import fastenv
    import httpx


    async def download_my_dotenvs(
        bucket_host: str,
        bucket_region: str,
        bucket_path_to_common_env: str = ".env.common",
        bucket_path_to_custom_env: str = ".env.custom",
    ) -> fastenv.DotEnv:
        config = fastenv.ObjectStorageConfig(
            bucket_host=bucket_host,
            bucket_region=bucket_region,
        )
        client = fastenv.ObjectStorageClient(config=config)
        env_common = await client.download(bucket_path_to_common_env)
        env_custom = await client.download(bucket_path_to_custom_env)
        return fastenv.DotEnv(env_common, env_custom)


    if __name__ == "__main__":
        bucket_host = "<BUCKET_NAME>.s3.<REGION>.backblazeb2.com"
        bucket_region = "<REGION>"
        anyio.run(download_my_dotenvs, bucket_host, bucket_region)

    ```

## Cloud object storage comparisons

### AWS S3

-   Pricing
    -   \$23/TB/month for storage
    -   \$90/TB/month outbound (also called download or egress), with further complex and expensive egress fees
    -   See the [Backblaze B2 pricing page](https://www.backblaze.com/b2/cloud-storage-pricing.html) for comparisons
    -   See [Backblaze Blog 2021-12-03: Why the world needs lower egress fees](https://www.backblaze.com/blog/why-the-world-needs-lower-egress-fees/) and [Cloudflare Blog 2021-07-23: AWS's egregious egress](https://blog.cloudflare.com/aws-egregious-egress/) for criticisms
-   Identity and Access Management (IAM):
    -   [AWS IAM in S3](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-access-control.html)
-   URIs:
    -   Path style URL: `https://s3.<region>.amazonaws.com/<bucketname>/<keyname>`. _Deprecated (see the [AWS blog](https://aws.amazon.com/blogs/aws/amazon-s3-path-deprecation-plan-the-rest-of-the-story/))_.
    -   [Virtual-hosted-style URL](https://docs.aws.amazon.com/AmazonS3/latest/userguide/VirtualHosting.html): `https://<bucketname>.s3.<region>.amazonaws.com/<keyname>`. _This is the recommended URL format_.
    -   S3 URI: `s3://<bucketname>/<keyname>`. _This method is only used for certain AWS tools like the AWS CLI (see [docs](https://awscli.amazonaws.com/v2/documentation/api/latest/reference/s3/index.html) and [source code](https://github.com/aws/aws-cli/blob/fa4b05b4bad8574441e4d969aa1ad58a30ff550d/awscli/customizations/s3/utils.py#L217-L250))_.
    -   [Presigned URLs](https://docs.aws.amazon.com/AmazonS3/latest/userguide/ShareObjectPreSignedURL.html)
-   [Bucket naming rules](https://docs.aws.amazon.com/AmazonS3/latest/userguide/UsingBucket.html):

    > An Amazon S3 bucket name is globally unique, and the namespace is shared by all AWS accounts. This means that after a bucket is created, the name of that bucket cannot be used by another AWS account in any AWS Region until the bucket is deleted.

### Azure Blob Storage

[Azure Blob Storage](https://docs.microsoft.com/en-us/azure/storage/blobs/storage-blobs-overview) is not S3-compatible, and will not be directly supported by fastenv. In downstream projects that store _.env_ file objects in Azure, users are welcome to download objects using the [Azure Python SDK](https://docs.microsoft.com/en-us/azure/storage/blobs/storage-quickstart-blobs-python), and then load the files with `fastenv.load_dotenv()` after download.

### Backblaze B2

-   [Pricing](https://www.backblaze.com/b2/cloud-storage-pricing.html):
    -   \$6/TB/month for storage (about 1/4 the price of S3)
    -   Outbound (also called download or egress) data transfer fees are 1/4 the price of S3
    -   See [Backblaze Blog 2021-12-03: Why the world needs lower egress fees](https://www.backblaze.com/blog/why-the-world-needs-lower-egress-fees/)
-   [S3-compatible API](https://www.backblaze.com/b2/docs/s3_compatible_api.html)\*
    -   Downloading and listing operations are S3-compatible
    -   \*Uploads are different, though there are [good reasons](https://www.backblaze.com/blog/design-thinking-b2-apis-the-hidden-costs-of-s3-compatibility/) for that (helps Backblaze keep pricing low)
-   URIs:
    -   Path style URL: `https://s3.<region>.backblazeb2.com/<bucketname>`
    -   Virtual-hosted-style URL: `https://<bucketname>.s3.<region>.backblazeb2.com`
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

-   [Pricing](https://developers.cloudflare.com/r2/platform/pricing/)
    -   \$15/TB/month for storage (about half the price of AWS S3, but over double the price of Backblaze B2)
-   [S3-compatible API](https://developers.cloudflare.com/r2/platform/s3-compatibility/api/)
-   URIs
    -   Regions are handled automatically. "When using the S3 API, the region for an R2 bucket is `auto`. For compatibility with tools that do not allow you to specify a region, an empty value and `us-east-1` will alias to the `auto` region."
    -   Cloudflare R2 URLs are different from other S3-compatible object storage platforms. The Cloudflare account ID is included in bucket URIs, but the region is not.
    -   Path style URL: `https://<ACCOUNT_ID>.r2.cloudflarestorage.com/<bucketname>`
    -   Virtual-hosted-style URL: `https://<BUCKET>.<ACCOUNT_ID>.r2.cloudflarestorage.com` (added [2022-05-16](https://developers.cloudflare.com/r2/platform/changelog/#2022-05-16), also see [cloudflare/cloudflare-docs#6405](https://github.com/cloudflare/cloudflare-docs/pull/6405)), though note that the docs on [using the AWS CLI with R2](https://developers.cloudflare.com/r2/examples/aws/aws-cli/) and and [using Boto3 with R2](https://developers.cloudflare.com/r2/examples/aws/boto3/) still show only path style URLs.
    -   Presigned URLs are supported
        -   Added [2022-06-17](https://developers.cloudflare.com/r2/platform/changelog/#2022-06-17)
        -   There may be CORS limitations on uploads due to lack of ability to set the `Access-Control-Allow-Origin` header ([cloudflare/cloudflare-docs#4455](https://github.com/cloudflare/cloudflare-docs/issues/4455)).
    -   [Presigned `POST` is not currently supported](https://developers.cloudflare.com/r2/api/s3/presigned-urls/#supported-http-methods).
-   Identity and Access Management (IAM):
    -   [Requires generation of a static access key](https://developers.cloudflare.com/r2/data-access/s3-api/tokens/). Does not appear to support temporary credentials from IAM roles (AWS session tokens). Does not appear to support OpenID Connect (OIDC).
    -   Access keys can be set to either read-only or edit permissions.
    -   Access keys can be scoped to specific Cloudflare products, Cloudflare accounts, and IP addresses.
-   Lifecycle policies
    -   Added [2023-03-16](https://developers.cloudflare.com/r2/reference/changelog/#2023-03-16) ([blog post](https://blog.cloudflare.com/introducing-object-lifecycle-management-for-cloudflare-r2/))
    -   [Docs](https://developers.cloudflare.com/r2/buckets/object-lifecycles/)
-   Docs
    -   [Cloudflare R2 docs](https://developers.cloudflare.com/r2/)
    -   [Cloudflare Blog 2021-07-23: AWS's egregious egress](https://blog.cloudflare.com/aws-egregious-egress/)
    -   [Cloudflare Blog 2021-09-28: Announcing Cloudflare R2 Storage](https://blog.cloudflare.com/introducing-r2-object-storage/)
    -   [Cloudflare Blog 2022-09-21: R2 is now Generally Available](https://blog.cloudflare.com/r2-ga/)

### DigitalOcean Spaces

-   Pricing: $5 monthly flat rate
    -   Up to 250GB of data storage
    -   No charge for inbound data transfer
    -   Up to 1TB of outbound data transfer (also called download or egress)
-   [S3-compatible API](https://docs.digitalocean.com/reference/api/spaces-api/)
-   URIs:
    -   Path style URL: `https://<region>.digitaloceanspaces.com/<bucketname>`
    -   Virtual-hosted-style URL: `https://<bucketname>.<region>.digitaloceanspaces.com`
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
    -   Virtual-hosted-style URLs?
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
    -   Virtual-hosted-style URL: `https://<bucketname>.<region>.linodeobjects.com`
    -   Presigned URLs are supported
-   Identity and Access Management (IAM):
    -   Minimal (access keys automatically access all buckets)
    -   Access keys cannot be created without paying the monthly fee first
-   Docs
    -   [Linode docs: Storage - Object Storage - Overview](https://www.linode.com/docs/products/storage/object-storage/)
    -   [Linode docs: Storage - Object Storage - Guides - Using the AWS SDK for Python (boto3) with Object Storage](https://www.linode.com/docs/products/storage/object-storage/guides/aws-sdk-for-python/)
