#!/usr/bin/env python3
from aws_cdk import App
from infrastructure.chatbot_stack import ChatbotStack
from config import get_config

config = get_config()
app = App()

ChatbotStack(app, config.get_stack_name(),
    env={
        "account": config.AWS_ACCOUNT,
        "region": config.AWS_REGION
    }
)

app.synth()
