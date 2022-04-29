import aws_cdk as core
import aws_cdk.assertions as assertions

from control_broker_consumer_example_config.control_broker_consumer_example_config_stack import ControlBrokerConsumerExampleConfigStack

# example tests. To run these tests, uncomment this file along with the example
# resource in control_broker_consumer_example_config/control_broker_consumer_example_config_stack.py
def test_sqs_queue_created():
    app = core.App()
    stack = ControlBrokerConsumerExampleConfigStack(app, "control-broker-consumer-example-config")
    template = assertions.Template.from_stack(stack)

#     template.has_resource_properties("AWS::SQS::Queue", {
#         "VisibilityTimeout": 300
#     })
