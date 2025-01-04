from typing import Callable
from abc import abstractmethod, ABC
import logging
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from .prices import OctopusPricesClient, Price

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Resolves circular import as it's only used
    # for typing.
    from .config import OctopusAgileScheduleConfig, OctopusGoScheduleConfig
    from .config import TrackedScheduleConfigCreator, CompleteConfig

from apscheduler.schedulers.background import BackgroundScheduler

class ScheduleProvider(ABC):
    @abstractmethod
    def run(self):
        pass


class PricingStrategy(ABC):
    """
    Contract for pre-defined or user defined price handling strategies.
    -
    This determines what logic should run at each half hourly period.
    """
    @abstractmethod
    def handle_price(self, price: Price, prices: list[Price]):
        """
        Define what to do when a price is considered cheap or expensive.
        
        Example
        ```python
        if price.value < 10 and position < 5:
            self.config.action_when_cheap(price)
        else:
            self.config.action_when_expensive(price)
        ```
        """
        pass

class DefaultPricingStrategy(PricingStrategy):
    """
    Simply determines if the price is within the cheapest prices to include and runs the appropriate action.
    """
    def __init__(self, config: "CompleteConfig"):
        self.config = config

    def _determine_cheapest_to_include(self, prices):
        if isinstance(self.config.prices_to_include, Callable):
            number_of_cheapest_to_include = self.config.prices_to_include(prices)

        if isinstance(self.config.prices_to_include, int):
            number_of_cheapest_to_include = self.config.prices_to_include
        
        return number_of_cheapest_to_include

    def handle_price(self, price: Price, prices: list[Price]):
        sorted_prices = sorted(prices, key=lambda obj: min(obj.value, obj.value))
        sorted_position = sorted_prices.index(price)

        number_of_cheapest_to_include = self._determine_cheapest_to_include(prices)

        if (sorted_position <= number_of_cheapest_to_include - 1):
            self.config.action_when_cheap(price)
        if (sorted_position > number_of_cheapest_to_include - 1):
            self.config.action_when_expensive(price)

class OctopusGoScheduleProvider(ScheduleProvider):
    def __init__(
            self,
            prices_client: OctopusPricesClient,
            config: "OctopusGoScheduleConfig",
            scheduler: BackgroundScheduler,
            tracked_schedule_config: "TrackedScheduleConfigCreator"
        ):
        self.prices_client = prices_client
        self.scheduler = scheduler
        self.tracked_schedule_config = tracked_schedule_config
        self.config = config

    def _interpolate_15_minutely_price_data(self, price_data: list[Price]) -> list[Price]:
        """
        Will convert the three prices into 15 min intervals only containing today.
        """
        # We want to generate 15 minute intervals between the datetime_from and datetime_to for each of the prices
        sorted_prices = sorted(price_data, key=lambda obj: obj.datetime_from)

        sorted_prices[0] = Price(
            value=sorted_prices[0].value,
            datetime_from=sorted_prices[0].datetime_from.replace(hour=0, minute=0),
            datetime_to=sorted_prices[0].datetime_from
        )

        sorted_prices[-1] = Price(
            value=sorted_prices[-1].value,
            datetime_from=sorted_prices[-1].datetime_to,
            datetime_to=sorted_prices[-1].datetime_to.replace(hour=0, minute=0)
        )
        
        new_price_data = []
        for price in price_data:
            intervals_to_generate = (price.datetime_to - price.datetime_from).total_seconds() / 60 / 15
            for i in range(int(intervals_to_generate)):
                new_price_data.append(
                    Price(
                        value=price.value,
                        datetime_from=price.datetime_from + timedelta(minutes=i*15),
                        datetime_to=price.datetime_from + timedelta(minutes=(i+1)*15)
                    )
                )

        return new_price_data

    def run(self):
        # In intelligent go/go land their days are between 5:30 and 5:30 in order to only get the two prices for the day
        today_date = datetime.now(timezone.utc)

        date_from = (datetime(
            hour=0,
            minute=0,
            year=today_date.year,
            month=today_date.month,
            day=today_date.day
        )).isoformat("T")

        date_to = datetime(
            hour=0,
            minute=0,
            year=today_date.year,
            month=today_date.month,
            day=today_date.day + 1    
        ).isoformat("T")

        product_prefix = "INTELLI" if self.config.is_intelligent == True else "GO"

        todays_prices = self.prices_client.get_prices_for_users_tariff_and_product(
            product_prefix=product_prefix, date_from=date_from, date_to=date_to
        )

        todays_interpolated_prices = self._interpolate_15_minutely_price_data(todays_prices)

        logging.info(f"Generating schedule for {len(todays_interpolated_prices)} prices")

        pricing_strategy_class = self.config._pricing_strategy or DefaultPricingStrategy

        for price in todays_interpolated_prices:
            pricing_strategy_class(self.tracked_schedule_config.get_config()).handle_price(price, prices=todays_interpolated_prices)

            def job(price: Price):
                def run_price_task():
                    pricing_strategy_class(self.config).handle_price(price, prices=todays_interpolated_prices)
                    
                return run_price_task

            logging.debug(f"Added new job for {price.datetime_from}")

            self.scheduler.add_job(
                func=job(price),
                trigger='date',
                run_date=price.datetime_from.replace(tzinfo=ZoneInfo("GMT")),
                misfire_grace_time=60*10,
                next_run_time=price.datetime_from.replace(tzinfo=ZoneInfo("GMT")),
            )

        logging.info("Schedule generated")


class OctopusAgileScheduleProvider(ScheduleProvider):
    def __init__(
            self,
            prices_client: OctopusPricesClient,
            config: "OctopusAgileScheduleConfig",
            scheduler: BackgroundScheduler,
            tracked_schedule_config: "TrackedScheduleConfigCreator"
        ):
        self.prices_client = prices_client
        self.config = config
        self.scheduler = scheduler
        self.tracked_schedule_config = tracked_schedule_config

    def run(self):
        today_date = datetime.now(timezone.utc)

        date_from = (datetime(
            hour=0,
            year=today_date.year,
            month=today_date.month,
            day=today_date.day
        )).isoformat("T")

        date_to = datetime(
            hour=23,
            year=today_date.year,
            month=today_date.month,
            day=today_date.day      
        ).isoformat("T")

        todays_prices = self.prices_client.get_prices_for_users_tariff_and_product("AGILE", date_from, date_to)

        logging.info(f"Generating schedule for {len(todays_prices)} prices")

        pricing_strategy_class = self.config._pricing_strategy or DefaultPricingStrategy

        for price in todays_prices:
            pricing_strategy_class(self.tracked_schedule_config.get_config()).handle_price(price, todays_prices)

            def job(price: Price):
                def run_price_task():
                    pricing_strategy_class(self.config).handle_price(price, todays_prices)
                    
                return run_price_task

            logging.debug(f"Added new job for {price.datetime_from}")

            # TODO: I can forsee people possibly want to do jobs within these half hourly blocks
            #       but this should be a future feature on request.
            self.scheduler.add_job(
                func=job(price),
                trigger='date',
                run_date=price.datetime_from.replace(tzinfo=ZoneInfo("GMT")),
                misfire_grace_time=60*15,
                next_run_time=price.datetime_from.replace(tzinfo=ZoneInfo("GMT"))
            )
    
        logging.info("Schedule generated")
