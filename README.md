# Model rocket flight calibration

Estimate actual apogee from OpenRocket simulations and measured flights, then
recommend a tested ballast setting for the 2027 American Rocketry Challenge.
The tool operates on one rocket configuration and one motor designation at a time.
No real flight data is included.

For a student explanation with derivations, worked examples, uncertainty
calculations, and practice questions, read the
[calibration study guide](CALIBRATION_STUDY_GUIDE.md).

## Competition objective

The [official 2027 rules](https://www.rocketrychallenge.org/wp-content/uploads/2027-American-Rocketry-Challenge-Rules-.pdf),
sections 4.3 through 4.6, specify an 800 ft qualification target, a 37 to 40 second
flight duration window, and a maximum total launch mass of 650 g. Two eggs must
return undamaged, and the rocket uses parachute recovery with its parts tethered
together. The scoring altitude comes from an approved scoring altimeter.
Finals altitude targets differ between flights and are within 775 to 825 ft.

For an otherwise valid flight, the altitude and duration penalty is:

```text
abs(measured_apogee_ft - target_ft)
    + 4 * max(37 - duration_s, 0, duration_s - 40)
```

Lower is better. This project checks the mass limit and computes this numerical
penalty when duration is supplied. It does not determine whether a flight meets
all competition rules. The altitude target is configurable; 800 ft is 243.84 m.

## Run

Install [uv](https://docs.astral.sh/uv/) or use Python 3.11 or newer with NumPy and
SciPy installed. With uv, project dependencies are installed on the first run:

```sh
uv run python -m rocket_calibration \
  --flights data/flights.csv \
  --candidates data/candidates.csv \
  --output outputs/recommendation.json
```

The CSV files in `data/` are empty templates. Fill them before running. For a
working example using explicitly synthetic data:

```sh
uv run python -m rocket_calibration \
  --flights examples/synthetic_flights.csv \
  --candidates examples/synthetic_candidates.csv \
  --synthetic \
  --output outputs/synthetic_recommendation.json
```

Use `--target-ft 775` for a different altitude objective. Use `--model offset` or
`--model linear` to choose a model explicitly; the default is `auto`.
With an existing Python environment, replace `uv run python` with `python`.

## Collect comparable records

Each flight needs the following columns. Units are part of the column names.

| Column | Meaning |
| --- | --- |
| `flight_id` | Unique flight identifier |
| `launch_date` | Local launch date, `YYYY-MM-DD`; used to group validation |
| `configuration` | Identifier for fixed airframe, finish, recovery setup, ballast mounting location, and design revision |
| `motor` | Exact motor designation, including delay |
| `launch_mass_g` | Measured total launch mass with motor, both eggs, electronics, and ballast |
| `ballast_g` | Added ballast, already included in total launch mass |
| `wind_speed_m_s` | Observed launch wind speed |
| `temperature_c` | Observed air temperature |
| `station_pressure_hpa` | Local absolute pressure, not a sea-level-adjusted weather report |
| `simulated_apogee_ft` | OpenRocket prediction matching this flight's mass and conditions |
| `measured_apogee_ft` | Scoring altimeter reading |
| `duration_s` | Optional total flight time; leave blank if unavailable |

Keep altitude referenced to the launch point. Retain the original `.ork` file,
OpenRocket version, simulation exports/settings, motor batch if available,
measured center of gravity, launch angle, rail setup, wind direction, and flight
observations alongside the records. Additional CSV columns are accepted. Version
the design and simulation settings so an existing simulation can be reproduced.
Wind speed alone cannot describe the full wind field or weathercocking.

Measure mass for every flight because eggs, motors, and repairs can change it.
Place ballast at the same fixed mounting location, and measure CG and check
stability for each setting. The configuration identifier must change after a
material change to geometry, finish, recovery, or ballast location. Use a
separate input file for each configuration and motor combination.

Only include comparable, representative flights in calibration. Record anomalous
flights separately and document any exclusion, such as premature deployment or
a damaged airframe. Do not discard a flight merely because its altitude is low.

The candidate CSV replaces `flight_id` with `candidate_id` and omits the measured
altitude, launch date, and duration. Each row is an OpenRocket simulation at a
proposed ballast setting under the same forecast weather. Candidate launch mass
minus ballast must be constant within 0.1 g. Enter the actual proposed launch mass;
do not add ballast twice. The program consumes scalar simulation results, and
does not run OpenRocket or parse `.ork` files.

OpenRocket supports measured mass/CG adjustments, adjustable ballast, and flight
data export. See its [official guidance](https://wiki.openrocket.info/Tips).
Match these inputs before fitting a correction.

## Launch plan

Budget 15 practice flights for a configuration with no established repeatability
record: three baseline flights, nine mass-calibration flights, and three held-out
confirmation flights. This is a proposed starting budget, not a statistical
guarantee. Comparable historical flights can supply the baseline, reducing the
new-flight budget to 12. Additional tuning or failures can require more flights.
The [ARC flight-testing briefing from January 2025](https://rocketrychallenge.org/wp-content/uploads/Flight-Testing-in-American-Rocketry-Challenge-January-2025.pdf)
reports that teams qualifying for Finals typically performed at least 15 test
flights. Use that briefing for general testing practice; use the 2027 rules for
current competition requirements.

Keep the airframe, finish, motor designation and delay, ballast mounting location,
recovery hardware and packing procedure, altimeter installation, and launch setup
consistent. Use motors from the same production batch where practical, and record
the batch. The experimental factor is ballast amount. Weigh the entire rocket
before every flight, including its replacement motor and eggs. Changing ballast
still changes CG, so each planned setting needs a stability and launch-performance
check before it is flown.

| Stage | Practice flights | What changes | Decision after the stage |
| --- | --- | --- | --- |
| Baseline | 1 through 3 | Nothing intentional; use the same middle ballast setting M | Establish preliminary repeatability and resolve deployment or trajectory problems |
| Mass calibration | 4 through 12 | Fly light L, middle M, and heavy H once each on each of three launch dates | Fit the discrepancy model and check whether its mass term improves date-held-out prediction |
| Confirmation | 13 through 15 | Freeze the model and selected ballast setting before these flights; use later launch dates | Compare predictions recorded before flight with actual altitude and duration |

### Baseline and ballast selection

Start with a setting that has already passed the team's flight-readiness checks.
Do not correct mass after a single ordinary altitude miss. Three baseline repeats
give an initial indication of variability, not a precise variance estimate.
If a trajectory, deployment, or hardware problem appears, address it immediately
and document the configuration change before collecting a new comparable baseline.

Choose L, M, and H from an OpenRocket mass sweep. Include enough adjustable ballast
at M that both lighter and heavier settings are possible. Avoid negative ballast,
the 650 g launch-mass ceiling, and unsuitable stability or rail-departure behavior.
Choose settings that span the target region after the preliminary altitude
correction. If existing data show that the target is outside this range, recenter
the planned settings before the calibration stage.

The altitude difference between adjacent mass settings should be appreciably
larger than baseline scatter. As an initial planning heuristic, aim for roughly
two to three times the estimated repeat-to-repeat altitude standard deviation.
For example, a hypothetical 10 ft standard deviation suggests testing settings
with about 20 to 30 ft predicted altitude separation. This is not a power calculation.
Derive the required grams from the rocket's simulated mass response; do not assume
a universal feet-per-gram correction or that heavier always flies lower. If only
very small altitude differences are feasible, plan more repetitions.

### Calibration order

Use a randomized order for L, M, and H within each date, writing it down in advance.
Each date should include every setting, rather than assigning one mass to each day.
An illustrative sequence is:

| Calibration date | First flight | Second flight | Third flight |
| --- | --- | --- | --- |
| 1 | M | L | H |
| 2 | H | M | L |
| 3 | L | H | M |

Draw the actual order randomly. Treat each date as a block, and split or postpone
a block if conditions change so much that its flights are no longer comparable.
This follows the principle of controlling nuisance variation through
[blocking and randomization](https://www.itl.nist.gov/div898/handbook/pri/section3/pri332.htm).
Keep each block reasonably close in time while following normal preparation and
inspection procedures. Reproduce each flight's observed mass and weather in its
OpenRocket simulation. The tool uses launch-date-held-out validation but does not
fit an explicit day-effect parameter. Flag a material within-day condition change
in the flight notes and assess it separately.

### Confirmation and decisions

Select the ballast using the calibration flights, then record each confirmation
prediction before ignition. Keep the last three flights out of fitting and model
selection until their prediction errors have been assessed. Spread them over at
least two later dates where practical, within the tested weather range.
If a setting or model is changed in response to these results, they become tuning
data and a fresh confirmation set is needed. Three confirmations are an initial
check, not proof of 95% coverage or of a low failure probability.

Choose an altitude tolerance and an acceptable expected score before confirmation.
For illustration, +/-10 ft is a team performance goal, not an ARC rule. Also assess
flight duration against the official 37 to 40 second window. Use the prediction
interval for an individual future flight when judging the altitude tolerance;
a confidence interval for the mean does not describe flight repeatability.

Use these decisions after collecting a block or confirmation set:

| Finding | Next action |
| --- | --- |
| Repeatable altitude error in the same direction | Adjust ballast using the fitted response, then repeat confirmation |
| Large scatter at unchanged settings | Investigate mass measurement, motor batch, launch behavior, deployment, and weather before chasing the latest altitude |
| Target lies beyond the tested mass range | Add a suitable new setting and repeat it, then refit and confirm |
| Confirmation errors change with mass or weather | Expand the experiment in that variable and reassess the correction model |
| Altitude is acceptable but duration misses its window | Tune recovery as a separate experiment; record a new configuration and recheck altitude |
| Predictions and observed variability meet the preset goal | Freeze the procedure and proceed to qualification |

Keep a contingency budget for extra blocks or recovery changes. More launches
reduce uncertainty in the estimated response, but they do not eliminate genuine
motor, atmosphere, trajectory, or preparation variation. The number of launches
needed depends on the altitude tolerance, observed scatter, and range of weather
conditions over which the team wants to make predictions. An unchanged configuration
with a tight mean estimate can still have an unacceptably broad next-flight interval.

Official qualification attempts are separate from the practice budget. The
[2027 rules, section 4.7](https://www.rocketrychallenge.org/wp-content/uploads/2027-American-Rocketry-Challenge-Rules-.pdf)
require at least two and allow at most three qualification attempts, with ranking
based on the best two qualified flights. Declare an official attempt before
ignition. A 15-practice-flight campaign therefore budgets 17 to 18 total launches
before any additional tuning or replacement flights, excluding Finals.

## Calibration and uncertainty

For each flight, form the simulation discrepancy:

```text
error_ft = measured_apogee_ft - simulated_apogee_ft
offset: error_ft = beta_0 + noise
linear: error_ft = beta_0 + beta_mass * (launch_mass_g - reference_mass_g) + noise
```

The reference mass is the mean training launch mass. Ordinary least squares fits
the correction, which is added to each candidate's OpenRocket altitude. The
OpenRocket mass response retains its original shape. A slope describes a
statistical discrepancy; it does not establish a physical drag coefficient or
prove that ballast alone caused the change.

At least four measured flights are required for an offset model and validation.
A linear model requires at least six flights, three distinct launch masses, and
estimable validation folds. These are computational minimums, not evidence that
the dataset is adequate. Follow the staged launch plan above, including repeats
at each ballast setting and independent confirmation on later dates.

With three or more launch dates, validation holds out all flights from one date
at a time. Otherwise it leaves out individual flights and warns that performance
on a new day is unestablished. `auto` selects the linear model only if its
validation mean absolute error is at least 10% lower than the offset model's.
This threshold is a conservative project convention, not a statistical test.
The report includes the raw simulation MAE and both available validation MAEs.
Model-selection validation is not an independent final test. Reserve later flights
to evaluate the complete selection and recommendation process.

For design vector x and residual standard deviation s, the next-flight predictive
scale is `s * sqrt(1 + x.T @ inverse(X.T @ X) @ x)`. A Student t distribution with
`n - p` degrees of freedom supplies the central 95% prediction interval and
expected absolute altitude penalty. The extra 1 includes flight-to-flight
variation, rather than reporting only uncertainty in the fitted mean.
The expected absolute penalty is integrated analytically under this distribution.
It can be positive even when predicted mean altitude equals the target.

These are nominal model-based intervals. They assume independent, normally
distributed errors with constant variance, a correct correction model, and
correctly matched simulation inputs. They do not include model-selection
uncertainty, forecast error, within-day correlation, or unobserved configuration
changes. Check future prediction coverage before trusting them. Near-zero
residual variation triggers a warning, not evidence of perfect predictability.
Apogee-only records cannot reliably separate motor, drag, trajectory, and sensor
errors. See [SciPy's Student t documentation](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.t.html)
for the distribution API.

## Recommendation

The JSON report gives corrected predictions, 95% prediction intervals, expected
altitude penalty, validation errors, per-flight discrepancies, and exclusions.
The selected candidate minimizes expected absolute altitude error among supplied
eligible settings. Ties favor less ballast. It is a discrete comparison of supplied
simulations, not an estimate of a continuous optimum.

A candidate is excluded from recommendation if total launch mass exceeds 650 g,
mass or ballast lies outside the observed range, or any recorded weather variable
lies outside its observed range. These checks use separate ranges and do not
establish that every combination inside them has been validated. Excluded
candidates remain visible with reasons; their extrapolated predictions should
not be trusted. If all candidates are excluded, `recommendation` is `null`.
The tool does not infer duration from apogee, optimize the full competition score,
or check stability and launch performance. Those need additional measurements
and checks by the team. A recommendation is provisional until tested in flight.

## Verify

```sh
uv run python -m unittest discover -s tests -v
```

Tests cover calibration recovery, uncertainty, numerical penalty integration,
day-grouped validation, model selection, input validation, mass constraints,
extrapolation, and the command-line workflow using synthetic records.
