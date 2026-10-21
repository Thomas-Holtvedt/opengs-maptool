class NumberSeriesExhaustedError(Exception):
    """Raised when a NumberSeries has been exhausted and cannot generate more IDs."""
    pass

class NumberSeries:
    def __init__(self, PREFIX, NUMBER_START, NUMBER_END):
        self.PREFIX: str = PREFIX
        self.NUMBER_END: int = NUMBER_END
        self.ID_LENGTH: int = len(str(NUMBER_END))
        self.number_next: int = NUMBER_START

    def get_id(self) -> str:
        if self.number_next > self.NUMBER_END:
            raise NumberSeriesExhaustedError(f"NumberSeries exceeded its limit of {self.NUMBER_END}.")

        formatted_number: str = self.PREFIX + \
            str(self.number_next).zfill(self.ID_LENGTH)
        self.number_next += 1
        return formatted_number
