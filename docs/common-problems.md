# Common problems

## [Highly common] I'm not seeing any logs

This is likely due to not having configured your logger in your python script, follow the example below:

```python
import logging

from energy_tariff_scheduler import PricingStrategy, Price, runner

logging.getLogger("energy_tariff_scheduler").setLevel(logging.INFO)
```

## [Possibly common] Octopus: The runner is using the incorrect product and prices

Currently the logic for finding your tariff is it fetches your account details from your provided account number, finds your most recent tariff, gets the tariff code for it and then tries its best to match the closest product code from the current active products provided by Octopus (where they are non-business type and within Octopus brand), here it's assumed that the product code contains as many characters as possible in the tariff code, such as if your tariff code is `E-1R-AGILE-FLEX-22-11-25-C` if a product doesn't exist for this it may match `AGILE-24-10-01`.

Obviously this isn't foolproof and a big assumption has been made here so expect it to fail, and if it does please raise it <a href="https://github.com/craigwh10/energy-tariff-scheduler/discussions/new?category=api-issues" target="_blank">on the API issues page</a> and provide relevant logs provided under the `DEBUG` level, an effort has been made to not log out any sensitive data but please be vigilant not to post any in the case of seeing any.

### My tariff isn't supported

If you hit this problem you should see this error (note the mismatch in the tariff and product that has been found):

```log
INFO:root:Latest tariff code: E-1R-VAR-22-11-01-M
DEBUG:urllib3.connectionpool:https://api.octopus.energy:443 "GET /v1/products/AGILE-24-10-01/electricity-tariffs/E-1R-VAR-22-11-01-M/standard-unit-rates/?period_from=2025-01-03T00:00:00&period_to=2025-01-03T23:00:00 HTTP/1.1" 404 58
The tariff code you are on isn't supported by this script, please read https://craigwh10.github.io/energy-tariff-scheduler/common-problems/#possibly-common-octopus-the-runner-isnt-finding-my-tariff-or-product
```

For the example referenced, the debug level is set as `DEBUG`.

## [Less common] The runner wont start because of the API not returning data

This library is build around third party API's, these can fail due to many reasons which are out of this libraries control.

I wouldn't reccomend spam retrying the script as this could lead to your IP being blacklisted, the script automatically tries to retry the failed call 3 times (with a 10s delay), it could take upwards of a few days for things to get rectified (as it's people on the other end who need to fix it), so just be patient with it and try every hour or so.

Also, when you see this happen be sure to start a discussion <a href="https://github.com/craigwh10/energy-tariff-scheduler/discussions/new?category=api-issues" target="_blank">on the API issues page</a> to make others aware that this is happening and to help with making the solution more resiliant to these sorts of issues.
