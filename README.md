# An example Consumer of Control Broker: Detective Controls via AWS Config

## Overview

[Control Broker](https://github.com/VerticalRelevance/control-broker) is a Policy as Code evaluation engine available via an API. Various Consumers can invoke this API to get evaluations of a given input against a series of policies expressed using the [Open Policy Agent](https://www.openpolicyagent.org) framework. This Policy-as-Code process codifies security and operational requirements into policy code, which in the case of OPA are written in the [Rego](https://www.openpolicyagent.org/docs/latest/policy-language/) language.

A common use case for OPA is a pre-deployment check in a Infrastructure-as-Code pipeline.

OPA can also be leveraged for Detective Controls that evaluate existing resources. [Resources supported by Cloud Control](https://docs.aws.amazon.com/cloudcontrolapi/latest/userguide/supported-resources.html) can be described by the  [GetResource](https://docs.aws.amazon.com/cloudcontrolapi/latest/APIReference/API_GetResource.html) Schema, which, when wrapped in a `Resources` key, is a Schema that can overlap with a raw Cloud Formation template schema.

This repository aims to deploy a minimal Detective Control environment that invokes the Control Broker endpoint at `/ConfigEvent` to get an evaluation on an [AWS Config Event](https://docs.aws.amazon.com/config/latest/developerguide/evaluate-config_develop-rules_example-events.html).


This `readme.md` will cover:

1. Setup the local Python environment
2. Deploy the Detective Control consumer Control Broker via Python [CDK](https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html)
3. Toggle the configuration of an ExampleApp resource to test the PaC evaluation


## 1. Setup the Local Python Environment

### Requirements

1. A running serverless instance of Control Broker. See setup [here](https://github.com/VerticalRelevance/control-broker)
2. A development environment capable of setting up a Python virtual environment

#### Tested with

This repository was tested with a [Cloud9](https://aws.amazon.com/cloud9/) IDE.

```
uname -a # (Cloud9) Linux ip-10-0-3-28.ec2.internal 4.14.320-243.544.amzn2.x86_64 #1 SMP Tue Aug 1 21:03:08 UTC 2023 x86_64 x86_64 x86_64 GNU/Linux
python3 -V # Python 3.9.6
```

### Fetch the Control Broker Invoke Url From the CloudFormation UI at `Outputs`

The CodePipeline stacks needs to know at which URL to invoke the Control Broker instance deployed in step 1.1. 

Set `control-broker/apigw-url` in [cdk.json](./cdk.json) to the value for the key that starts with `ControlBrokerApiConfigEventHandlerUrl`


```
{
    "control-broker/apigw-url":"https://MY_API_ID.execute-api.us-east-1.amazonaws.com/ConfigEvent"
}
```
#### Tested with

This repository was tested with a [Cloud9](https://aws.amazon.com/cloud9/) IDE.

```bash
uname -a # (Cloud9) Linux ip-10-0-3-28.ec2.internal 4.14.320-243.544.amzn2.x86_64 #1 SMP Tue Aug 1 21:03:08 UTC 2023 x86_64 x86_64 x86_64 GNU/Linux
python3 -V # Python 3.9.6
npm -v # 9.8.1
node -v # v16.20.1
npm update -g typescript
npm install -g aws-cdk --force
cdk --version # 2.92.0 (build bf62e55)
```
To setup the Python CDK environment in a new Cloud9 instance, consider: 

```bash

# 0. setup
uname -a # tested on: Linux ip-10-0-3-28.ec2.internal 4.14.320-243.544.amzn2.x86_64 #1 SMP Tue Aug 1 21:03:08 UTC 2023 x86_64 x86_64 x86_64 GNU/Linux
sudo rm -f /var/run/yum.pid
sudo rm -rf /var/lib/yum/history
sudo rm -f /home/ec2-user/environment/README.md
sudo yum -y update

# 1. upgrade python
cd ~
wget https://www.python.org/ftp/python/3.9.6/Python-3.9.6.tgz
tar xzvf Python-3.9.6.tgz
cd Python-3.9.6
./configure
make
sudo make install
cd ~
sudo rm -f Python-3.9.6.tgz
sudo rm -rf Python-3.9.6
export PATH="/usr/local/bin:$PATH"
exec $SHELL
python3 -V
pip3 install urllib3==1.26.6 # requests

# 2. set venv
cat >> ~/.bashrc << EOF

alias ve='python3 -m venv venv'
alias ae='deactivate &> /dev/null; source ./venv/bin/activate'
alias pu='python3 -m pip install -U pip setuptools wheel'
alias pit='python3 -m pip install pip-tools'
alias pc='pip-compile'
alias ps='pip-sync'
alias start='ve && ae && pu && pit'
alias cdd='cdk deploy --all --require-approval=never'
EOF
exec $SHELL
```

2. Deploy the Detective Control consumer Control Broker via Python [CDK](https://docs.aws.amazon.com/cdk/v2/guide/getting_started.html)


Clone this repository and perform the following setup from the root of this repository.


```bash
start # build venv
pc && ps # install packages using pip-tools
cdd # cdk deploy
```

## 3. Toggle the configuration of an ExampleApp resource to test the PaC evaluation

Our ExampleApp consists of two SQS queues. One has

```
content_based_deduplication = toggled_boolean,
```
the other has
```
content_based_deduplication = not toggled_boolean,
```

where
```
toggled_boolean_path='./dev/tracked_by_config/toggled_boolean.json'
```


This [OPA policy](https://github.com/VerticalRelevance/control-broker-module-private/blob/cb-core/supplementary_files/policy_as_code/python/opa_policies/cloudformation/AWS--SQS--Queue__cfn01__dedup.rego) performs a simple operational check on that CloudFormation template. It applies to resources of type "AWS::SQS::Queue", and requires that `ContentBasedDeduplication` be `true`.

The result is that with each `cdk deploy`, the stack will edit the queues to alter that field of interest. This generates Config Events which are available to view in the Cloud Watch Logs of the [invoked\_by\_config lambda](./supplementary_files/lambdas/invoked_by_config), which passes that Config Event to Control Broker endpoint at `/ConfigEvent` to get an evaluation.

This evaluation decision is returned as an evaluation to the AWS Config Rule that starts with `CBConsumerConfig-SQSPoC`. The End-to-End test of that evaluation is tracked in an AWS Step Functions State Machine named `ConfigEventProcessing`.

Use `cdk deploy` to trigger evaluations, and view the Step Functions and AWS Config console to track their progress.

For a complete list of example Consumers of Control Broker, including a CodePipeline implementation of the IaC pipeline referenced above, see [here](https://github.com/VerticalRelevance/control-broker)