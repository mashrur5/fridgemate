from enum import Enum


class Location(Enum):
    """Where an item is stored. The location changes how long food lasts."""

    FRIDGE = "fridge"
    FREEZER = "freezer"
    PANTRY = "pantry"
