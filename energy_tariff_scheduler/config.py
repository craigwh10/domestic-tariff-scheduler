import inspect
import logging

from typing import Callable, Optional, Type
from pydantic import BaseModel, PositiveInt, field_validator

from .prices import Price
from .schedules import PricingStrategy

class BaseConfig(BaseModel):
    pass

class SimpleActionsConfig(BaseConfig):
    """
    At a minimum, this will be the expected config, but I think even this could change if people want more granularity than
    "expensive" and "cheap"
    """
    action_when_cheap: Callable[[Price], None]
    action_when_expensive: Callable[[Price], None]

    @field_validator("action_when_cheap", "action_when_expensive", mode="before")
    def validate_custom_actions(cls, value, info):
        sig = inspect.signature(value)
        params = sig.parameters

        if len(params) != 1:
            raise SystemExit(
                f"Usage error:\n\n"
                f"You are missing a required parameter in function '{info.field_name}'"+\
                f"\n\nFix: '{value.__name__}(price: Price):'"+\
                f"\n\nCheck other action is like this too otherwise the error will repeat."
                # TODO: Add a reference to error page
            )
        return value
    
    model_config = dict(
        extra="allow"
    )

class PricesToIncludeConfig(BaseConfig):
    prices_to_include: PositiveInt | Callable[[list[Price]], int]

    @field_validator("prices_to_include", mode="before")
    def validation_prices_to_include_custom_method(cls, value, info):
        if isinstance(value, float):
            raise SystemExit(
                f"Runner usage error:\n\n"+\
                f"When passing an value into '{info.field_name}' this needs to be an integer greater than 0"
                # TODO: Add a reference to error page
            ) 
        if isinstance(value, int):
            if value < 0:
                raise SystemExit(
                    f"Runner usage error:\n\n"+\
                    f"When passing an value into '{info.field_name}' this needs to be an integer greater than 0"
                    # TODO: Add a reference to error page
                )
        if callable(value):
            sig = inspect.signature(value)
            params = sig.parameters

            if len(params) != 1:
                raise SystemExit(
                    f"Runner usage error:\n\n"+\
                    f"You are missing a required parameter in function '{info.field_name}'"+\
                    f"\n\nFix: '{value.__name__}(prices: list[Price]):'"
                    # TODO: Add a reference to error page
                )

        return value
    
class PricingStrategyConfig(BaseConfig):
    _pricing_strategy: Optional["PricingStrategy"] = None

    def add_custom_pricing_strategy(self, pricing_strategy: Type[PricingStrategy]):
        """
        Adds a custom pricing strategy to the configuration.
        You pass in a class, not an instance as the config is injected later.
        ```
        """
        # it's done this way to allow for the custom strategy to access the config
        if not issubclass(pricing_strategy, PricingStrategy):
            raise SystemExit(
                f"Usage error:\n\n"+\
                f"The custom pricing strategy {pricing_strategy.__name__} must inherit from PricingStrategy\n\nException fix: use 'from schedules import PricingStrategy' and 'class {pricing_strategy.__name__}(PricingStrategy):'"
            )

        try:
            instance = pricing_strategy(self)
            # accessing this will raise if it's not implemented
            # it doesn't need a raise NotImplemented within the method, ABC throws by default if
            # it's not implemented as TypeError
            instance.handle_price 
            # This also checks if __init__ is meeting the instance contract so no
            # need for a __init__ sig check. 
        except TypeError:
            raise SystemExit(
                f"Usage error:\n\n"+\
                f"Your custom pricing strategy '{pricing_strategy.__name__}' has improper setup"+\
                f"\n\nFix: Check your implementation for differences"+\
                f"\n\nclass {pricing_strategy.__name__}(PricingStrategy):\n"+\
                f"  def __init__(self, config):\n"+\
                f"      self.config = config\n\n"+\
                f"  def handle_price(self, price: Price, prices: list[Price]):\n"+\
                f"      // your code\n"
            )

        handle_price_sig = inspect.signature(instance.handle_price)
        params = handle_price_sig.parameters

        if len(params) < 2:
            raise SystemExit(
                f"Usage error:\n\n"+\
                f"You are missing required parameters in function 'handle_price' on '{pricing_strategy.__name__}'"+\
                f"\n\nFix: Minimally use 'handle_price(self, price: Price, prices: list[Price]):'"
            )

        self._pricing_strategy = pricing_strategy

        return self
    
class CompleteConfig(SimpleActionsConfig, PricesToIncludeConfig, PricingStrategyConfig):
    pass

class OctopusGoScheduleConfig(CompleteConfig):
    #  Go is 10 prices, Intelligent is 12 prices
    is_intelligent: bool = False

class OctopusAgileScheduleConfig(CompleteConfig):
    # Agile is 46 prices
    pass

class TrackedSchedule:
    price: Price
    action: str

    def __init__(self, price: Price, action: str):
        self.price = price
        self.action = action

class TrackedScheduleConfigCreator:
    calls: list[TrackedSchedule]
    tracked_config: SimpleActionsConfig

    def __init__(self, config: SimpleActionsConfig):
        self.tracked_config = config.model_copy()
        self.calls = []

        action_when_cheap_inspector = self._tracker("action_when_cheap", self.calls)
        action_when_expensive_inspector = self._tracker("action_when_expensive", self.calls)
        setattr(self.tracked_config, "action_when_cheap", action_when_cheap_inspector)
        setattr(self.tracked_config, "action_when_expensive", action_when_expensive_inspector)

    def get_config(self):
        return self.tracked_config

    def _tracker(self, action, calls: list[TrackedSchedule]):
        def func(price: Price):
            calls.append(TrackedSchedule(price=price, action=action))
            pass
        return func

    def log_schedule(self):
        sorted_calls = sorted(self.calls, key=lambda tracked_schedule: tracked_schedule.price.datetime_from)
        calls_as_logs = [f"{schedule.price.datetime_from.strftime('%H:%M')}, action: {schedule.action}, price: {schedule.price.value}p/kWh" for schedule in sorted_calls]
        log_content = "\n".join(calls_as_logs)
        logging.info(f"\n\nTodays schedule (this includes already passed jobs):\n\n{log_content}\n")

class OctopusAPIAuthConfig(BaseModel):
    api_key: str
    account_number: str

    model_config = dict(
        # this is strict for config but not for field classes
        extra="forbid"
    )
