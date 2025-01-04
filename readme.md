# Energy Tariff Scheduler

Enables smart actions based on daily pricing from utilities.

```sh
pip install energy-tariff-scheduler
```

Full documentation: [https://craigwh10.github.io/energy-tariff-scheduler/](https://craigwh10.github.io/energy-tariff-scheduler/)

## Supported tariff's (so far)

- [Octopus Agile](https://octopus.energy/smart/agile/)
- [Octopus Go](https://octopus.energy/smart/go/)
- [Intelligent Octopus Go](https://octopus.energy/smart/intelligent-octopus-go/)

## FAQ

> Do I need my account number?

Yes, you currently need your account number and API key for Octopus tariffs, this is documented in <a href="https://craigwh10.github.io/energy-tariff-scheduler/getting-started/getting-api-key-and-account-no/" target="_blank">Getting API key and Account number</a>, this is required to fetch your latest tariff code from Octopus so that the library can best try match it with current available products.

> Why are no actions running between 11pm and 12am for Octopus Agile?

This is due to data availability, Octopus only provide pricing data from 12am-11:00pm.

## Structure

- [prices.py](./prices.py): responsible for fetching data from external APIs and transform for usage based on contracts
- [schedules.py](./schedules.py): responsible for creating schedules and applying pricing logic
- [runner.py](./runner.py): responsible for the interface between users and the program
- [config.py](./config.py): responsible for providing validated user inputted configuration and providing a way to track user passed methods
