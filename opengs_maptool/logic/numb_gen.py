class NumberSeries:
    def __init__(self, PREFIX, NUMBER_START, NUMBER_END) -> None:
        self.PREFIX: str = PREFIX
        self.NUMBER_END: int = NUMBER_END
        self.ID_LENGTH: int = len(str(NUMBER_END))
        self.number_next: int = NUMBER_START

    def get_id(self) -> str | None:
        if self.number_next > self.NUMBER_END:
            print("ERROR: No more available numbers!")
            return None

        formatted_number: str = self.PREFIX + \
            str(self.number_next).zfill(self.ID_LENGTH)
        self.number_next += 1
        return formatted_number
