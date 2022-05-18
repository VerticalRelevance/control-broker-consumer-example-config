#!/usr/bin/env python3
import os

import aws_cdk as cdk

from stacks.config_stack import ControlBrokerConsumerExampleConfigStack

app = cdk.App()

ControlBrokerConsumerExampleConfigStack(app, "CBConsumerConfig",

    env=cdk.Environment(account=os.getenv('CDK_DEFAULT_ACCOUNT'), region=os.getenv('CDK_DEFAULT_REGION')),
    control_broker_apigw_url=app.node.try_get_context("control-broker/apigw-url"),

)

app.synth()
