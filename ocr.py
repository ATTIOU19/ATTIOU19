from typing import Optional, Callable, List, Iterator
from concurrent.futures import ThreadPoolExecutor, Future
import numpy as np
import torch
from transformers import (
    AutoTokenizer, AutoModelForImageTextToText, NougatProcessor,
    TextStreamer, TextIteratorStreamer,
    )

MAX_NEW_TOKENS = 4096


# class TextStreamerCallback(TextStreamer):
#     def __init__(
#         self,
#         tokenizer: AutoTokenizer,
#         callback_func: Callable,
#         skip_prompt: bool=True,
#         skip_special_tokens: bool=True
#     ) -> None:
#         super().__init__(
#             tokenizer, skip_prompt=skip_prompt,
#             skip_special_tokens=skip_special_tokens
#             )
#         self.callback_func = callback_func
#
#     def on_finalized_text(self, text: str, stream_end: bool = False) -> None:
#         self.callback_func(text, stream_end)


class Processor:
    def __init__(self) -> None:
        self.repos_id = "facebook/nougat-base"
        self.processor = NougatProcessor.from_pretrained(self.repos_id)

    def preprocess(self, images: List[np.ndarray]) -> torch.Tensor:
        processor_outputs = self.processor(images=images, return_tensors="pt")
        pixel_values = processor_outputs.pixel_values
        return pixel_values

    def postprocess(self, outs: object) -> str:
        seqs = self.processor.batch_decode(outs, skip_special_tokens=True)
        text = self.processor.post_process_generation(seqs, fix_markdown=True)
        return text


class Estimator:
    def __init__(
        self,
        max_new_tokens: int=MAX_NEW_TOKENS,
        min_length: int = 1,
    ) -> None:
        self.max_new_tokens = max_new_tokens
        self.min_length = min_length
        self.repos_id ="facebook/nougat-base"
        # self.tokenizer = AutoTokenizer.from_pretrained(self.repos_id)
        self.model = AutoModelForImageTextToText.from_pretrained(self.repos_id)

    def forward(
        self,
        pixel_values: torch.Tensor,
        streamer: TextStreamer=None,
    ) -> object:
        outs = self.model.generate(
            pixel_values, max_new_tokens=self.max_new_tokens,
            min_length=self.min_length,
            streamer=streamer,
            # bad_words_ids=[[self.tokenizer.unk_token_id]]
            # Avoid generating unknown tokens;
            )
        return outs

    def __call__(self, pixel_values: torch.Tensor) -> object:
        return self.forward(pixel_values)


class Transcription(Estimator):
    def __init__(
        self,
        processor: Processor,
        max_new_tokens: int=MAX_NEW_TOKENS,
        min_length: int=1,
    ) -> None:
        super().__init__(max_new_tokens, min_length)
        self.processor = processor

    def predict(self, images: List[np.ndarray]) -> str:
        pixel_values = self.processor.preprocess(images)
        outputs = self.forward(pixel_values)
        string = self.processor.postprocess(outputs)
        return string


class StreamTranscription(Estimator):
    def __init__(
        self,
        processor: Processor,
        max_new_tokens: int = MAX_NEW_TOKENS,
        min_length: int = 1,
        max_workers: int = 4,
    ) -> None:
        super().__init__(max_new_tokens, min_length)
        self.processor = processor
        self.max_workers = max_workers
        self.repos_id = "facebook/nougat-base"
        self.tokenizer = AutoTokenizer.from_pretrained(self.repos_id)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)

    def _transcription_function(
        self,
        image: List[np.ndarray],
        streamer: TextIteratorStreamer,

        return_result: bool=False,
    ) -> Optional[str]:
        pixel_values = self.processor.preprocess(image)
        outputs = self.forward(pixel_values, streamer)
        if return_result:
            text = self.processor.postprocess(outputs)
            return text

    def predict(
        self,
        images: List[np.ndarray],
        skip_prompt: bool=True,
        return_result: bool=False,
    ) -> List[TextIteratorStreamer]:
        streamers = []
        for image in images:
            streamer = TextIteratorStreamer(
                self.tokenizer, skip_prompt=skip_prompt
                )
            gen_kwargs = dict(
                image=image, streamer=streamer, return_result=return_result
                )
            self.executor.submit(self._transcription_function, **gen_kwargs)
            # self._transcription_function(**gen_kwargs)
            streamers.append(streamer)
        return streamers

    def shutdown(self, wait: bool=True, cancel_futures: bool=False) -> None:
        self.executor.shutdown(wait=wait, cancel_futures=cancel_futures)
        ...


def main() -> int:
    """Main function to run an inference on an image loaded from file."""
    import os
    import argparse
    from PIL import Image

    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", type=str)
    parser.add_argument(
        "-o", "--outputs", type=str,
        help="The path to file where we want to save texts generated."
        )
    args = parser.parse_args()
    inputs = args.inputs
    outputs = args.outputs

    if not os.path.isfile(inputs):
        print("No such file at \"" + inputs + "\".")
        return 2

    # collected_tokens = []

    # def token_callback(text: str, is_end: bool):
    #     """Callback called for each token generated."""
    #     if text.strip():  # Ignore empty tokens;
    #         collected_tokens.append(text)
    #         print(text, end=" ", flush=True)

    ocr_processor = Processor()
    ocr = StreamTranscription(ocr_processor, max_new_tokens=8192)
    # streamer = TextStreamerCallback(ocr.tokenizer, token_callback)
    # ocr.set_streamer(streamer)

    image = Image.open(inputs).convert("RGB")
    image = np.array(image)
    streamers = ocr.predict([image], return_result=(outputs is not None))
    texts_read = []
    print("Generation started...")
    for i, streamer in enumerate(streamers, 1):
        text_read = ""
        print("Image: " + str(i))
        for text in streamer:
            text_read += text
            print(text, end='', flush=True)
        texts_read.append(text_read)
    ocr.shutdown()
    print("\n")

    if outputs is not None:
        print("Saving of the result into file located at: " + str(outputs))
        with open(outputs, mode='w', encoding='utf-8') as file:
            for text in texts_read:
                file.write(text)
                file.write("\n---\n")
    return 0


if __name__ == '__main__':
    try:
        code = main()
        exit(code)
    except KeyboardInterrupt as e:
        print("KeyboardInterrupt: " + str(e))
        print("\033[91mInference canceled by user!\033[0m")
        exit(125)
