#!/usr/bin/env python3
# python -m samples.AgentGPT
import json
import platform

from termcolor import colored

from lib.chat_session import ChatSession
from lib.chat_slash_config import ChatSlashConfig

if platform.system() == "Darwin":
    # So that input can handle Kanji & delete
    import readline  # noqa: F401


with open("./manifests/manifests.json", "r") as f:
    manifests = json.load(f)


class Main:
    def __init__(self, config: ChatSlashConfig):
        self.config = config
        manifestA = self.config.manifests.get("chomsky")
        manifestB = self.config.manifests.get("tawara")

        self.sessionA = ChatSession(self.config, manifest=manifestA, agent_name="chomsky")
        self.sessionB = ChatSession(self.config, manifest=manifestB, agent_name="tawara")

    def process_llm(self, session):
        try:
            (res, function_call) = session.call_llm()

            if res:
                self.print_bot(res, session)

            if function_call:
                (
                    function_message,
                    function_name,
                    should_call_llm,
                ) = function_call.process_function_call(
                    session.manifest,
                    session.history,
                    None,
                )
                if function_message:
                    self.print_function(function_name, function_message)

                if should_call_llm:
                    self.process_llm(session)

        except Exception as e:
            print(colored(f"Exception: Restarting the chat :{e}", "red"))

    """
    the main loop
    """

    def start(self, theme):
        print(f"\033[92m\033[1mテーマ\033[95m\033[0m: {theme}")
        self.sessionB.append_user_question(theme)

        self.talk_with_input(theme, self.sessionA)
        while True:
            last_message_a = self.sessionA.history.last()
            self.talk_with_input(last_message_a["content"], self.sessionB)
            last_message_b = self.sessionB.history.last()
            self.talk_with_input(last_message_b["content"], self.sessionA)

    def talk_with_input(self, question, session):
        session.append_user_question(question)
        self.process_llm(session)

    def print_bot(self, message, session):
        print(f"\033[92m\033[1m{session.botName}\033[95m\033[0m: {message}")

    def print_function(self, function_name, message):
        print(f"\033[95m\033[1mfunction({function_name}): \033[95m\033[0m{message}")


if __name__ == "__main__":
    config = ChatSlashConfig("./manifests/agents")
    main = Main(config)
    main.start("自由と国家について")
