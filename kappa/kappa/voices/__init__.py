"""Voice engines. Every voice takes mono float32 audio at ENGINE_SR and returns the same amount."""

ENGINE_SR = 48000


class Voice:
    """Base class: a streaming audio transformer."""

    #: samples per call to process(); the engine always feeds exactly this many
    block_size = 1024

    def process(self, block):
        raise NotImplementedError

    def set_params(self, **params):
        pass

    def reset(self):
        pass

    def close(self):
        pass


class Passthrough(Voice):
    block_size = 480

    def process(self, block):
        return block
