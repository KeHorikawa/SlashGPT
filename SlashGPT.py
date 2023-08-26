#!/usr/bin/env python3
import json
import os
import platform
import re

from gtts import gTTS
from playsound import playsound
from termcolor import colored

from lib.chat_config import ChatConfig
from lib.chat_session import ChatSession
from lib.function.jupyter_runtime import PythonRuntime
from lib.llms.models import get_llm_model_from_key, llm_models
from lib.utils.help import LONG_HELP, ONELINE_HELP
from lib.utils.utils import (COLOR_DEBUG, COLOR_ERROR, COLOR_INFO,
                             COLOR_WARNING, InputStyle)

if platform.system() == "Darwin":
    # So that input can handle Kanji & delete
    import readline  # noqa: F401


"""
utility functions for Main class
"""


def play_text(text, lang):
    audio_obj = gTTS(text=text, lang=lang, slow=False)
    audio_obj.save("./output/audio.mp3")
    playsound("./output/audio.mp3")


with open("./manifests/manifests.json", "r") as f:
    manifests = json.load(f)

"""
Main is a singleton, which process the input from the user and manage chat sessions.
"""


class Main:
    def __init__(self, config: ChatConfig, manifest_key: str):
        self.config = config

        self.exit = False
        self.runtime = PythonRuntime("./output/notebooks")
        self.switch_session(manifest_key)

    """
    switchSession terminate the current chat session and start a new.
    The key specifies the AI agent.
    """

    def switch_session(self, manifest_key: str, intro: bool = True):
        if manifest_key is None:
            self.session = ChatSession(self.config)
            return
        if self.config.exist_manifest(manifest_key):
            self.session = ChatSession(self.config, manifest_key=manifest_key)
            if self.config.verbose:
                print(
                    colored(
                        f"Activating: {self.session.title} (model={self.session.llm_model.name()}, temperature={self.session.temperature}, max_token={self.session.llm_model.max_token()})",
                        COLOR_INFO,
                    )
                )
            else:
                print(colored(f"Activating: {self.session.title}", COLOR_INFO))
            if self.session.manifest.get("notebook"):
                (result, _) = self.runtime.create_notebook(
                    self.session.llm_model.name()
                )
                print(
                    colored(
                        f"Created a notebook: {result.get('notebook_name')}", COLOR_INFO
                    )
                )

            if intro:
                self.session.set_intro()
            if self.session.intro_message:
                self.print_bot(self.session.intro_message)
        else:
            print(colored(f"Invalid slash command: {manifest_key}", COLOR_ERROR))

    def parse_question(self, question: str):
        key = question[1:].strip()
        commands = re.split(r"\s+", key)
        return (key, commands)

    def detect_input_style(self, question: str):
        (key, commands) = self.parse_question(question)
        if len(question) == 0:
            return InputStyle.HELP
        elif key[:6] == "sample":
            return InputStyle.SAMPLE
        elif question[0] == "/":
            return InputStyle.SLASH
        else:
            return InputStyle.TALK

    def display_oneline_help(self):
        print(ONELINE_HELP)

    def process_sample(self, question: str):
        (key, commands) = self.parse_question(question)
        if commands[0] == "sample" and len(commands) > 1:
            sub_key = commands[1]
            sub_manifest_data = self.config.get_manifest_data(sub_key)
            if sub_manifest_data:
                sample = sub_manifest_data.get("sample")
                if sample:
                    print(sample)
                    return sample
            else:
                agents = self.session.manifest.get("agents")
                if agents:
                    print("/sample {agent}: " + ", ".join(agents))
                else:
                    print(colored(f"Error: No manifest named '{sub_key}'", COLOR_ERROR))
        elif key[:6] == "sample":
            sample = self.session.manifest.get(key)
            if sample:
                print(sample)
                return sample
            print(colored(f"Error: No {key} in the manifest file", COLOR_ERROR))
        return None

    """
    If the question start with "/", process it as a Slash command.
    Otherwise, return (roleInput, question) as is.
    Notice that some Slash commands returns (role, question) as well.
    """

    def process_slash(self, question: str):
        (key, commands) = self.parse_question(question)
        if commands[0] == "help":
            if len(commands) == 1:
                print(LONG_HELP)
                list = "\n".join(self.config.help_list())
                print(f"Agents:\n{list}")
            if len(commands) == 2:
                manifest_data = self.config.get_manifest_data(commands[1])
                if manifest_data:
                    print(json.dumps(manifest_data, indent=2))
        elif key == "bye":
            self.runtime.stop()
            self.exit = True
        elif key == "verbose" or key == "v":
            self.config.verbose = not self.config.verbose
            print(colored(f"Verbose Mode: {self.config.verbose}", COLOR_DEBUG))
        elif commands[0] == "audio":
            if len(commands) == 1:
                if self.config.audio:
                    self.config.audio = None
                else:
                    self.config.audio = "en"
            elif commands[1] == "off":
                self.config.audio = None
            else:
                self.config.audio = commands[1]
            print(f"Audio mode: {self.config.audio}")
        elif key == "prompt":
            if self.session.history.len() >= 1:
                print(self.session.history.get_data(0, "content"))
            if self.config.verbose and self.session.functions:
                print(colored(self.session.functions, COLOR_DEBUG))
        elif key == "history":
            print(json.dumps(self.session.history.messages(), indent=2))
        elif key == "functions":
            if self.session.functions:
                print(json.dumps(self.session.functions, indent=2))
        elif commands[0] == "llm" or commands[0] == "llms":
            if len(commands) > 1 and llm_models.get(commands[1]):
                llm_model = get_llm_model_from_key(commands[1])
                self.session.set_llm_model(llm_model)
            else:
                print("/llm: " + ",".join(llm_models.keys()))
        elif key == "new":
            self.switch_session(self.session.manifest_key, intro=False)
        elif commands[0] == "autotest":
            file_name = commands[1] if len(commands) > 1 else "default"
            file_path = f"./test/{file_name}.json"
            if not os.path.exists(file_path):
                print(colored(f"No test script named {file_name}", COLOR_WARNING))
                return
            self.config.verbose = True
            with open(file_path, "r") as f:
                scripts = json.load(f)
                self.switch_manifests(scripts.get("manifests") or "main")
                for message in scripts.get("messages"):
                    self.test(**message)
            self.config.verbose = False
        elif commands[0] == "switch":
            if len(commands) > 1 and manifests.get(commands[1]):
                self.switch_manifests(commands[1])
            else:
                print("/switch {manifest}: " + ", ".join(manifests.keys()))
        elif self.config.has_manifest(key):
            self.switch_session(key)
        else:
            print(colored(f"Invalid slash command: {key}", COLOR_ERROR))

    def switch_manifests(self, key):
        m = manifests[key]
        self.config.load_manifests("./" + m["manifests_dir"])
        self.switch_session(m["default_manifest_key"])

    def test(self, agent, message):
        self.switch_session(agent)
        question = self.process_sample(message)
        self.session.append_user_question(question)
        self.process_llm()

    def process_llm(self):
        try:
            # Ask LLM to generate a response.
            (res, function_call) = self.session.call_llm()

            if res:
                self.print_bot(res)

                if self.config.audio:
                    play_text(res, self.config.audio)

            if function_call:
                (action_data, action_method) = function_call.emit_data()
                if action_method:
                    # All emit methods must be processed here
                    if action_method == "switch_session":
                        self.switch_session(action_data.get("manifest"), intro=False)
                        self.session.append_user_question(action_data.get("message"))
                        self.process_llm()
                else:
                    (
                        function_message,
                        function_name,
                        should_call_llm,
                    ) = function_call.process_function_call(
                        self.session.history,
                        self.runtime,
                        self.config.verbose,
                    )
                    if function_message:
                        self.print_function(function_name, function_message)

                    if should_call_llm:
                        self.process_llm()

        except Exception as e:
            print(colored(f"Exception: Restarting the chat :{e}", COLOR_ERROR))
            self.switch_session(self.session.manifest_key)
            if self.config.verbose:
                raise

    """
    the main loop
    """

    def start(self):
        while not self.exit:
            self.talk_with_input()

    def talk_with_input(self):
        question = input(
            f"\033[95m\033[1m{self.session.userName}: \033[95m\033[0m"
        ).strip()
        mode = self.detect_input_style(question)
        if mode == InputStyle.HELP:
            self.display_oneline_help()
        elif mode == InputStyle.SLASH:
            self.process_slash(question)
        else:
            if mode == InputStyle.SAMPLE:
                question = self.process_sample(question)

            if question:
                self.session.append_user_question(
                    self.session.manifest.format_question(question)
                )
                self.process_llm()

    def print_bot(self, message):
        print(f"\033[92m\033[1m{self.session.botName}\033[95m\033[0m: {message}")

    def print_user(self, message):
        print(f"\033[95m\033[1m{self.session.userName}: \033[95m\033[0m{message}")

    def print_function(self, function_name, message):
        print(f"\033[95m\033[1mfunction({function_name}): \033[95m\033[0m{message}")


if __name__ == "__main__":
    config = ChatConfig("./manifests/main")
    print(ONELINE_HELP)
    main = Main(config, "dispatcher")
    main.start()
