# git2cc

git2cc (Git to CodeCommit) is a solution for syncing repositories, that do not support any AWS integration natively, with AWS CodeCommit. It includes a stack of all required resources and a lambda function that performs actual synchronization. This allows you to integrate any repository with AWS Code Suite.

The solution consists of a bunch of resources described below. Any IAM resources used in the template stick to the least privilege principle.

## Installation

#### Pre-requisites

You need AWS API access credentials linking to a user/role with IAM capabilities to install the required resources.

Your repository must allow a trigger/hook to publish commit messages to AWS SNS (via CLI or SDK). 

You need user and password to your repository, as well as an IAM user that would be able to publish to SNS.


#### Git module installation

As of September 2019, python git module is not available in AWS Lambda, hence we need to add git support along with the `git2cc.py` lambda. I have re-used https://github.com/eredi93/lambda-git/. Assuming `$PWD` is `git2cc`. 
```
git clone https://github.com/eredi93/lambda-git/ /tmp/lambda-git
cp -R /tmp/lambda-git/git/ lambda/git/
rm -rf /tmp/lambda-git
```

#### Stack deployment

Create CloudFormation package in an S3 bucket and deploy the stack from there, using packaged template.

_Note: As $S3_BUCKET set a bucket you own to store the package in._

```
S3_BUCKET=your_bucket_name
aws cloudformation package --template-file git2cc.yml --s3-bucket ${S3_BUCKET} --output-template-file /tmp/packaged-git2cc.yml
aws cloudformation deploy --template-file /tmp/packaged-git2cc.yml --stack-name git2cc-lamba-resources --capabilities CAPABILITY_NAMED_IAM
```

This will create stack `git2cc-lamba-resources` with following resources:
* `Git2CodeCommitLambda` - Lambda that performs the sync from your repo to CodeCommit
  * `AWSLambdaBasicExecutionRole` - IAM role used by this function, only necessary permissions
  * `LambdaInvokePermission` - allows the lambda to be triggered by SNS
* `CreateGitCredsForGit2CodeCommitLambda` - custom resource to create git credentials for CodeCommit (unfortunately so called _Service Specific Credentials_ are not natively supported by CloudFormation)
  * `InlineLambdaExecutionRole` - a role that allows creation of _Service Specific Credentials_ and store them in SSM by the custom resource
    * `CodeCommitLambdaIAMUser` - the CodeCommit user, defined by `GitCredentialsResource` - the actual _Service Specific Credentials_ resource
* `Git2ccSNSTopic`
  * `Git2ccSNSTopicPolicy` - policy to allow a user to publish to the SNS topic, which results in executing the code2cc lambda, you may want to change the 

#### Configuration

This is the tricky part, where you may need to tune this to work with your git repository.

First, go to the newly deployed Lambda and set your repository credantials in following environmental variables:
- src_repo_user
- src_repo_pass

If you haven't done this as a prerequisite, to create a user, allow it to publish to SNS permissions and give it API access keys. On your repository side, you need to create a hook, a trigger, or somehow manually trigger publish to SNS. 

At a minimum the SNS message shall contain the following:
```
{
    "repository": {
        "name": "my-fancy-repo",
        "git_http_url": "http://example.com/kormik/my-fancy-repo.git"
    },
    "ref": "refs/heads/master"
}
```

You can test it like this:

```
TOPIC_ARN=arn:aws:sns:<region>:<account_id>:git2cc-topic
aws sns publish --topic-arn ${TOPIC_ARN} --message '{
    "repository": {
        "name": "my-fancy-repo",
        "git_http_url": "http://example.com/kormik/my-fancy-repo.git"
    },
    "ref": "refs/heads/master"
}' 
```

_Note: you can extract the topic ARN from your stack outputs._

#### Troubleshooting

In case of issues, start troubleshooting by looking at CloudWatch log group */aws/lambda/Git2CodeCommit*.

If all OK, consider setting lambda's logLevel variable to _ERROR_ or _WARNING_ to prevent noise in CW.