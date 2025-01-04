from .schedules import DefaultPricingStrategy, OctopusAgileScheduleProvider, OctopusGoScheduleProvider, PricingStrategy
from .config import OctopusAPIAuthConfig, OctopusAgileScheduleConfig, OctopusGoScheduleConfig, TrackedScheduleConfigCreator
from .prices import OctopusCurrentTariffAndProductClient, OctopusPricesClient, Price 

import logging
from typing import Callable, Optional, Type
import time

from apscheduler.schedulers.background import BackgroundScheduler

"""
Current tariff support:
https://craigwh10.github.io/energy-tariff-scheduler/#current-supported-supplier-tariffs
"""

class ApScheduleSchedulerFilter(logging.Filter):
    def filter(self, record):
        if record.getMessage().startswith('Added job'):
            return False
        if record.getMessage().startswith('Adding new job'):
            return False
        if record.getMessage().startswith('Removed job'):
            # This is covered by a log saying jobs before will be missed.
            return False
        if record.getMessage().startswith('Adding job tentatively'):
            # This is covered by a log saying jobs before will be missed.
            return False
        if record.getMessage().startswith('Scheduler started'):
            # This is covered by a log saying jobs before will be missed.
            return False
        return True
    
class ApScheduleExecutorsFilter(logging.Filter):
    def filter(self, record):
        if record.getMessage().startswith('Run time of job'):
            # This is covered by a log saying jobs before will be missed.
            return False
        return True
     
logging.getLogger("apscheduler.scheduler").addFilter(
    ApScheduleSchedulerFilter()
)

logging.getLogger("apscheduler.executors.default").addFilter(
    ApScheduleExecutorsFilter()
)

def run_octopus_go_tariff_schedule(
        api_key: str,
        account_number: str,
        action_when_cheap: Callable[[Optional[Price]], None],
        action_when_expensive: Callable[[Optional[Price]], None],
        pricing_strategy: Optional[Type[PricingStrategy]] = DefaultPricingStrategy,
        is_intelligent: bool = False,
        prices_to_include: int | Callable[[list[Price]], int] | None = None,
):
    """
    Runs a schedule with half hourly jobs based on the Octopus Go tariff prices.
    
    Args:
        api_key: Octopus Energy API key.
        account_number: Octopus Energy account number.
        prices_to_include: The number of prices to include or a callable that determines the number dynamically from available prices.
        action_when_cheap: Action to execute when the price is in cheap period of go.
        action_when_expensive: Action to execute when the price is in expensive period of go.
        pricing_strategy: Custom pricing strategy to handle the prices.
        is_intelligent: If the tariff is intelligent or regular go.
    """
    continuous_scheduler = BackgroundScheduler()
    cron_scheduler = BackgroundScheduler()

    def set_daily_schedule() -> list[str]:
        # Go: 00:30 - 05:30, Intelligent: 11:30 - 5:30, people aren't encouraged to choose price amounts here as they're fixed*.
        # I have heard that intelligent can sometimes give more, but it's rare, not handling this.
        prices_to_include_for_go = prices_to_include or 48 if is_intelligent else 40
        config = OctopusGoScheduleConfig(
            prices_to_include=prices_to_include_for_go,
            action_when_cheap=action_when_cheap,
            action_when_expensive=action_when_expensive,
            is_intelligent=is_intelligent
        ).add_custom_pricing_strategy(
            pricing_strategy
        )
        
        tracked_schedule_config = TrackedScheduleConfigCreator(
            config=config,
        )

        api_auth_config = OctopusAPIAuthConfig(
            api_key=api_key,
            account_number=account_number
        )

        current_tariff_and_product_client = OctopusCurrentTariffAndProductClient(
            auth_config=api_auth_config
        )

        OctopusGoScheduleProvider(
            prices_client=OctopusPricesClient(
                auth_config=api_auth_config,
                tariff_and_product_client=current_tariff_and_product_client
            ),
            config=config,
            scheduler=continuous_scheduler,
            tracked_schedule_config=tracked_schedule_config,
        ).run()

        tracked_schedule_config.log_schedule()

    cron_scheduler.add_job(
        func=set_daily_schedule,
        trigger="cron",
        hour=0,
        minute=0
    )
    set_daily_schedule()

    cron_scheduler.start()
    continuous_scheduler.start()

    try:
        while True:
            # This is extremely important,
            # no sleep would lead to excessive CPU usage
            time.sleep(0.01)
    except (KeyboardInterrupt, SystemExit):
        continuous_scheduler.shutdown()
        cron_scheduler.shutdown()

def run_octopus_agile_tariff_schedule(
        api_key: str,
        account_number: str,
        prices_to_include: int | Callable[[list[Price]], int],
        action_when_cheap: Callable[[Optional[Price]], None],
        action_when_expensive: Callable[[Optional[Price]], None],
        pricing_strategy: Optional[Type[PricingStrategy]] = DefaultPricingStrategy,
    ):
    """
    Runs a schedule with half hourly jobs based on the Octopus Agile tariff prices.
    
    Args:
        api_key: Octopus Energy API key.
        account_number: Octopus Energy account number.
        prices_to_include: The number of prices to include or a callable that determines the number dynamically from available prices.
        action_when_cheap: Action to execute when the price is considered cheap.
        action_when_expensive: Action to execute when the price is considered expensive.
        pricing_strategy: Custom pricing strategy to handle the prices.
        
    Example Custom Pricing Strategy (Optional - default is just picking the cheapest `prices_to_include` prices):
    ```python
    from custom_sms import SMS
    import requests
    import logging
    from energy_tariff_scheduler import runner, PricingStrategy, Price

    class CustomPricingStrategy(PricingStrategy):
        def __init__(self, config: ScheduleConfig):
            self.config = config # for access to other set configuration

        def _get_carbon_intensity(self, price: Price):
            res = requests.get(f"https://api.carbonintensity.org.uk/intensity/{price.datetime_from}")
            return res.json()["data"][0]["intensity"]["actual"]

        def handle_price(self, price: Price, prices: list[Price]):
            if price.value < 5 and self._get_carbon_intensity(price) < 100:
                self.config.action_when_cheap(price)
            else:
                self.config.action_when_expensive(price)

    def switch_shelly_on_and_alert(price: Price):
        logging.info(f"Price is cheap: {price}")
        SMS.send(f"Price is cheap ({price}p/kWh), turning on shelly")
        requests.get("http://<shelly_ip>/relay/0?turn=on")

    def switch_shelly_off_and_alert(price: Price):
        logging.info(f"Price is expensive: {price}")
        SMS.send(f"Price is expensive ({price}p/kWh), turning off shelly")    
        requests.get("http://<shelly_ip>/relay/0?turn=off")

    runner.run_octopus_agile_tariff_schedule(
        prices_to_include=5, # 5 opportunties to trigger "action_when_cheap"
        action_when_cheap=switch_shelly_on_and_alert,
        action_when_expensive=switch_shelly_off_and_alert,
        pricing_strategy=CustomPricingStrategy,
        api_key="api_key (BROUGHT IN SAFELY)",
        account_number="account_number (BROUGHT IN SAFELY)"
    )
    ```
    """
    continuous_scheduler = BackgroundScheduler()
    cron_scheduler = BackgroundScheduler()

    def set_daily_schedule() -> list[str]:
        config = OctopusAgileScheduleConfig(
            prices_to_include=prices_to_include,
            action_when_cheap=action_when_cheap,
            action_when_expensive=action_when_expensive,
        ).add_custom_pricing_strategy(
            pricing_strategy
        )
        
        tracked_schedule_config = TrackedScheduleConfigCreator(
            config=config,
        )

        api_auth_config = OctopusAPIAuthConfig(
            api_key=api_key,
            account_number=account_number
        )

        current_tariff_and_product_client = OctopusCurrentTariffAndProductClient(
            auth_config=api_auth_config
        )

        OctopusAgileScheduleProvider(
            prices_client=OctopusPricesClient(
                auth_config=api_auth_config,
                tariff_and_product_client=current_tariff_and_product_client
            ),
            config=config,
            scheduler=continuous_scheduler,
            tracked_schedule_config=tracked_schedule_config
        ).run()

        tracked_schedule_config.log_schedule()

    cron_scheduler.add_job(
        func=set_daily_schedule,
        trigger="cron",
        hour=0,
        minute=0
    )

    set_daily_schedule()

    cron_scheduler.start()
    continuous_scheduler.start()

    try:
        while True:
            # This is extremely important,
            # no sleep would lead to excessive CPU usage
            time.sleep(0.01)
    except (KeyboardInterrupt, SystemExit):
        continuous_scheduler.shutdown()
        cron_scheduler.shutdown()
    
