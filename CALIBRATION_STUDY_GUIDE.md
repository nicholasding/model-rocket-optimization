# Understanding rocket flight calibration

A study guide for students using OpenRocket and real flight records

## How to use this guide

The question we want to answer is:

> Given our rocket, motor, weather, and added ballast, what altitude should we
> expect in a real flight, and how uncertain is that prediction?

This guide develops the method used in [the calibration tool](rocket_calibration.py).
Start with sections 1 through 8 for the main idea and a worked calculation.
Sections 9 through 15 explain prediction, experiments, and launch decisions.
Sections 16 and 17 connect the mathematics to the program. The appendix gives
optional matrix and calculus details. Practice questions and answers follow.

Prerequisites: averages, algebra, graphs, and square roots. Calculus and matrix
algebra are optional. All numerical teaching examples are **synthetic**, not
measurements of the team's rocket. The six-flight hand calculation is separate
from the twelve-flight example shipped with the project.

## 1. The two jobs: simulate and calibrate

OpenRocket represents the rocket and its flight physics. Its output changes when
we change mass, motor, launch setup, or atmospheric conditions.

The real rocket can behave differently because the representation is imperfect:
actual surface finish, motor output, launch trajectory, and measurements differ.
Calibration learns the difference that remains after we enter the measured inputs.

Our model is:

$$
\text{real altitude}
= \text{simulated altitude}
+ \text{systematic correction}
+ \text{remaining variation}.
$$

For example, if a matching simulation predicts 850 ft and the measured flight
reaches 820 ft, the observed discrepancy is -30 ft. A correction of -30 ft would
move that simulation to the measurement. However, one flight does not establish
that every future flight needs exactly this correction.

Two different questions must be answered:

1. **Bias:** Does the simulation tend to predict too high or too low?
2. **Repeatability:** How much do repeated flights vary around their expected altitude?

A rocket may have a correct average and still be inconsistent. Another may be
consistent but miss the target by the same amount every time.

The first situation requires reducing variability. The second may be improved
by adjusting ballast using a calibrated response.

## 2. Why added mass does not have a universal altitude effect

For an approximately vertical ascent in still air, an illustrative force model is:

$$
\frac{dh}{dt}=v,
\qquad
m(t)\frac{dv}{dt}
= F_T(t)-m(t)g-\frac12\rho C_D A\,v|v|.
$$

| Symbol | Meaning | SI unit |
| --- | --- | --- |
| $h$ | Height above the launch point | m |
| $v$ | Vertical velocity, positive upward | m/s |
| $t$ | Time | s |
| $m(t)$ | Instantaneous mass, decreasing during motor burn | kg |
| $F_T(t)$ | Motor thrust | N |
| $g$ | Gravitational acceleration | m/s² |
| $\rho$ | Air density | kg/m³ |
| $C_D$ | Drag coefficient | dimensionless |
| $A$ | Reference area used with that drag coefficient | m² |

During upward flight, $v|v|=v^2$, so drag opposes ascent.
This simplified equation omits three-dimensional motion and wind. In wind,
aerodynamics depend on velocity relative to the air, and their direction matters.
OpenRocket handles a richer flight model than this teaching equation.

Dividing the force equation by mass shows the competing effects:

$$
\frac{dv}{dt}
=\frac{F_T(t)}{m(t)}-g-\frac{\rho C_D A}{2m(t)}v|v|.
$$

At the same speed, a heavier rocket gets less acceleration from a given thrust,
but also less deceleration from a given drag force. Its speed history changes
as well. Therefore the final effect on apogee depends on the whole trajectory.
An optimum mass can exist; heavier does not universally mean lower.

The coefficient and density can vary during flight. We are not assuming that a
single constant $C_D$ explains all observed errors.
See [NASA's discussion of rocket aerodynamic forces](https://www1.grc.nasa.gov/beginners-guide-to-aeronautics/rocket-aerodynamics/)
for physical background.

**Mass and weight are different:** mass is in kilograms; weight is the force $mg$
in newtons. Our ballast inputs are masses in grams.

Use SI units in a force equation. Useful conversions are:

$$
1\text{ g}=0.001\text{ kg},
\qquad
1\text{ ft}=0.3048\text{ m},
\qquad
1\text{ hPa}=100\text{ Pa}.
$$

The statistical calibration can use grams and feet consistently because its
coefficients carry those units.

## 3. Define the data before fitting anything

For flight $i$, write:

| Symbol | Meaning |
| --- | --- |
| $m_i$ | Measured total launch mass in grams |
| $b_i$ | Added ballast in grams, already included in $m_i$ |
| $\mathbf w_i$ | Weather and launch inputs for this flight |
| $S_i=S(m_i,\mathbf w_i)$ | Matching OpenRocket apogee in feet |
| $Y_i$ | Measured apogee in feet |
| $r_i=Y_i-S_i$ | Observed simulation discrepancy in feet |
| $H_\star$ | Desired altitude, normally 800 ft for qualification |

Use the same motor designation and fixed rocket configuration for the dataset.
Measure total launch mass every flight, including the motor, eggs, electronics,
and ballast. Reproduce that mass and observed conditions in the simulation.

For a proposed launch with fixed non-ballast mass:

$$
m_{\text{launch}}=m_{\text{base}}+b.
$$

If the measured base mass is 500 g and ballast is 30 g, total launch mass is 530 g.
Do not add the ballast a second time to a total mass that already includes it.
The actual base mass may change when eggs or motors are replaced.

Weather belongs in the matching simulation first. Otherwise we might incorrectly
learn a mass correction that is actually compensating for changing weather.
The current correction model does not separately regress on wind, pressure, or
temperature; those are simulation inputs and tested-range checks.

Record local station pressure, not sea-level-adjusted pressure. Keep the altitude
reference consistent with the scoring altimeter's height above the launch point.
The [README data dictionary](README.md#collect-comparable-records) explains the CSVs.

## 4. Model A: a constant correction

The simplest model is:

$$
Y_i=S_i+\beta_0+\epsilon_i,
\qquad
r_i=\beta_0+\epsilon_i.
$$

Here $\beta_0$ is an unknown systematic correction and $\epsilon_i$ is remaining
variation. We assume its conditional average is zero. This assumption means the
systematic part has been adequately represented over the conditions being modeled.

The estimated correction is the mean discrepancy:

$$
\widehat\beta_0=\overline r=\frac1n\sum_{i=1}^n r_i.
$$

A hat means an estimate from data; a bar means an average.

For discrepancies of -28, -32, -31, and -29 ft:

$$
\widehat\beta_0=\frac{-28-32-31-29}{4}=-30\text{ ft}.
$$

The corrected prediction for a new simulation of 830 ft is:

$$
\widehat Y_{\text{new}}=830-30=800\text{ ft}.
$$

**Intuition:** shift OpenRocket's altitude-versus-mass curve up or down. Keep its
shape. This can be useful when a small dataset supports a consistent bias but
does not yet support an additional mass effect.

## 5. Model B: a correction that depends on launch mass

The simulation discrepancy may change with mass:

$$
Y_i=S_i+\beta_0+\beta_1(m_i-m_{\text{ref}})+\epsilon_i.
$$

The program chooses $m_{\text{ref}}=\overline m$, the mean training launch mass.

| Parameter | Interpretation | Unit |
| --- | --- | --- |
| $\beta_0$ | Correction at the reference mass | ft |
| $\beta_1$ | Change in correction per extra gram | ft/g |

For example:

$$
\widehat\delta(m)=-30-0.5(m-520).
$$

At 520 g, subtract 30 ft from OpenRocket. At 540 g, the additive correction is:

$$
-30-0.5(540-520)=-40\text{ ft}.
$$

The negative slope means the simulation overprediction grows with mass over this
tested range.

**Important:** $\beta_1$ is the slope of the correction, not the total altitude
response. OpenRocket already changes altitude when mass changes. We add this
extra correction to that existing response.

Centering mass at its mean also makes the intercept easy to interpret. It is
the correction at a typical measured mass, rather than at an unphysical 0 g.

This is an empirical local model. A fitted mass slope does not prove that mass
caused every discrepancy, or identify a particular aerodynamic parameter.

## 6. How least squares chooses the correction

Define $x_i=m_i-\overline m$. For any proposed coefficients, the unexplained
residual is:

$$
e_i=r_i-(\beta_0+\beta_1x_i).
$$

Do not confuse two quantities:

- $r_i=Y_i-S_i$: discrepancy before calibration.
- $e_i=Y_i-\widehat Y_i$: residual after fitting the calibration.

Least squares selects coefficients that minimize:

$$
Q(\beta_0,\beta_1)
=\sum_{i=1}^n \left[r_i-\beta_0-\beta_1x_i\right]^2.
$$

Squaring prevents positive and negative residuals from canceling and gives
larger misses more influence.
For centered masses, the solution is:

$$
\widehat\beta_0=\overline r,
\qquad
\widehat\beta_1=
\frac{\sum_i(m_i-\overline m)(r_i-\overline r)}
     {\sum_i(m_i-\overline m)^2}.
$$

The numerator measures whether discrepancies change with mass. The denominator
measures how much mass variation the experiment contains.

If all launch masses are identical, the denominator is zero. Such flights can
teach us about bias and repeatability, but cannot identify a mass slope.

These are the standard straight-line least-squares formulas applied to our
simulation discrepancies. [NIST gives the general formulas](https://www.itl.nist.gov/div898/handbook/pmd/section4/pmd431.htm).
The appendix derives them for this example.

## 7. A complete hand calculation

The following six flights are invented for arithmetic practice. Assume simulations
match their flight inputs. We fit the linear correction explicitly here; this
table alone is not a model-selection or independent validation exercise.

| Flight | Launch mass $m_i$, g | Simulation $S_i$, ft | Measured $Y_i$, ft | Discrepancy $r_i$, ft |
| --- | ---: | ---: | ---: | ---: |
| 1 | 500 | 910 | 892 | -18 |
| 2 | 500 | 910 | 888 | -22 |
| 3 | 520 | 860 | 832 | -28 |
| 4 | 520 | 860 | 828 | -32 |
| 5 | 540 | 810 | 772 | -38 |
| 6 | 540 | 810 | 768 | -42 |

The means are:

$$
\overline m=520\text{ g},
\qquad
\overline r=-30\text{ ft}.
$$

The centered masses are $-20,-20,0,0,20,20$ g.
The centered discrepancies are $12,8,2,-2,-8,-12$ ft.

Calculate:

$$
S_{xx}=\sum_i(m_i-\overline m)^2
=400+400+0+0+400+400=1600\text{ g}^2,
$$

$$
S_{xr}=\sum_i(m_i-\overline m)(r_i-\overline r)
=-240-160+0+0-160-240=-800\text{ g ft}.
$$

Therefore:

$$
\widehat\beta_1=\frac{-800}{1600}=-0.5\text{ ft/g},
\qquad
\widehat\beta_0=-30\text{ ft}.
$$

Our fitted prediction is:

$$
\boxed{\widehat Y(m,\mathbf w)
=S(m,\mathbf w)-30-0.5(m-520)}.
$$

Suppose a candidate simulation at 530 g predicts 835 ft. Its correction is:

$$
\widehat\delta(530)=-30-0.5(10)=-35\text{ ft}.
$$

Its corrected mean prediction is:

$$
\widehat Y(530)=835-35=800\text{ ft}.
$$

The fitted corrections at 500, 520, and 540 g are -20, -30, and -40 ft.
The six residuals after calibration are consequently:

$$
e_i=2,-2,2,-2,2,-2\text{ ft}.
$$

We have removed the systematic mass trend. Small variation remains.

## 8. Estimate the remaining variation

The estimated residual standard deviation is:

$$
s=\sqrt{\frac{\sum_i e_i^2}{n-p}},
$$

where $p$ is the number of fitted coefficients:

- Offset model: $p=1$.
- Linear correction: $p=2$.

The quantity $\nu=n-p$ is called the residual degrees of freedom.
Fitting coefficients uses information from the data, so dividing by $n-p$
accounts for those fitted constraints.

In the hand example:

$$
\sum_i e_i^2=6(2^2)=24\text{ ft}^2,
\qquad
\nu=6-2=4,
$$

$$
s=\sqrt{24/4}=\sqrt6\approx2.449\text{ ft}.
$$

This estimates the scale of unexplained flight variation under the model.
It includes whatever unexplained variation the dataset contains, including
measurement error. It is not a measurement of motor variability alone.
It is not a maximum possible miss and is not the same as MAE. Squaring residuals
gives larger deviations more influence in this variation estimate.

The total spread across all observed altitudes is not the same quantity:
changing mass deliberately changed the expected altitude.

## 9. Two kinds of uncertainty

### 9.1 Uncertainty in the expected altitude

We estimated coefficients from a finite sample. A different sample would give
slightly different coefficients and a different predicted mean.

For the linear correction define the leverage at a proposed mass:

$$
\ell(m)=\frac1n+\frac{(m-\overline m)^2}{S_{xx}}.
$$

The standard error of the estimated mean correction is:

$$
\operatorname{SE}_{\text{mean}}(m)=s\sqrt{\ell(m)}.
$$

The first term decreases with more flights. The second term grows as we predict
farther from the mean training mass. Spreading test masses helps estimate the
slope, but wider mass spacing does not replace repeats.

For the offset-only model, $\ell=1/n$.

### 9.2 Uncertainty in one future flight

Even if the average altitude were known perfectly, the next flight would still
vary. Include that remaining variation:

$$
a(m)=s\sqrt{1+\ell(m)}.
$$

The extra **1** is essential. It represents a new flight's variation around the
true mean, in addition to our uncertainty in that mean.

Under a fixed correct linear model with independent normal errors of constant
variance, the standardized prediction error follows a Student t distribution
with $\nu=n-p$ degrees of freedom. The nominal 95% prediction interval is:

$$
\boxed{\widehat Y(m)\ \pm\ t_{0.975,\nu}\,a(m)}.
$$

The t critical value allows for uncertainty in estimating the noise scale.
It is larger for small samples and approaches 1.96 as degrees of freedom grow.
The 0.975 quantile leaves 2.5% in each tail of a symmetric distribution, with
the middle 95% between the negative and positive critical values.

In the hand example at 530 g:

$$
\ell=\frac16+\frac{10^2}{1600}=0.229167,
\qquad
a=\sqrt6\sqrt{1.229167}=2.715695\text{ ft}.
$$

Since $t_{0.975,4}\approx2.776445$:

$$
\text{95% next-flight interval}
=800\pm7.539978
\approx[792.46,\ 807.54]\text{ ft}.
$$

The corresponding confidence interval for the expected altitude is narrower:

$$
800\pm2.776445\sqrt6\sqrt{0.229167}
=800\pm3.255670\text{ ft}.
$$

| Question | Interval in the hand example |
| --- | --- |
| How uncertain is the mean altitude? | Approximately 796.74 to 803.26 ft |
| How uncertain is one new flight? | Approximately 792.46 to 807.54 ft |

Use the second interval when judging an individual launch.

A nominal 95% prediction method has 95% long-run coverage under its assumptions.
It does not promise that the next apogee will fall inside the computed range, or
that 95% coverage survives an incorrect model or model selection.

Technical detail: $a$ is the **scale** of the t predictive distribution, not
its exact standard deviation. For $\nu>2$, that distribution's standard
deviation is $a\sqrt{\nu/(\nu-2)}$.
[SciPy documents the t distribution and its scale parameter](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.t.html).

## 10. Why a better fit is not automatically a better prediction

The linear correction contains the offset model as the special case $\beta_1=0$.
It can therefore fit training data at least as well in squared error. That does
not establish that its extra slope helps predict a future flight.

The program evaluates predictions on data excluded from fitting.

With at least three launch dates:

1. Remove all flights from one date.
2. Fit each correction using the remaining dates.
3. Predict the excluded flights.
4. Repeat for every date.
5. Average the absolute prediction errors across all excluded flights.

This is leave-one-launch-date-out validation. It tests prediction on an excluded
day. Predicting another flight from an already observed day can give an overly
optimistic impression when weather and preparation are unusually similar.

For held-out predictions $\widehat Y_i^{(-d)}$, the mean absolute error is:

$$
\operatorname{MAE}
=\frac1n\sum_i\left|Y_i-\widehat Y_i^{(-d)}\right|.
$$

The superscript means the prediction was fitted without that flight's date.
The program averages across flights; dates with more flights have more weight.
When there are fewer than three dates, it leaves out individual flights and warns
that performance on a new day has not been established.

In automatic mode, choose the linear correction only when its validation MAE is
strictly smaller and no more than 90% of the offset model's MAE:

$$
\operatorname{MAE}_{\text{linear}}
\leq0.90\,\operatorname{MAE}_{\text{offset}}.
$$

The program also requires enough data and estimable validation folds. The 10%
threshold is a project convention, not a significance test or a 90% confidence level.
If both models have zero validation error, it retains the offset model.

Compare both against the uncalibrated simulation too:

$$
\operatorname{MAE}_{\text{raw}}=\frac1n\sum_i|Y_i-S_i|.
$$

If calibration does not improve validation MAE over the raw simulation, the tool
warns that its recommendation is unvalidated. It does not automatically switch
to an uncalibrated recommendation.

Keep a final confirmation set separate from this selection process. Once a
confirmation flight influences a model choice or adjustment, it becomes tuning
data and fresh confirmation is needed.

## 11. Convert corrected altitude into a ballast decision

For an otherwise valid 2027 qualification flight, the altitude and duration score is:

$$
S_{\text{flight}}
=|Y-800|
+4\max(37-\tau,\ 0,\ \tau-40),
$$

where altitude $Y$ is in feet and total duration $\tau$ is in seconds.
The qualification altitude is 800 ft, the duration window is 37 to 40 seconds,
and total launch mass cannot exceed 650 g. Finals use different altitude targets
within 775 to 825 ft. See [the official 2027 rules, sections 4.3 through 4.6](https://www.rocketrychallenge.org/wp-content/uploads/2027-American-Rocketry-Challenge-Rules-.pdf).

Our tool ranks the altitude part only because its calibration inputs do not
describe duration well enough to predict it.

### 11.1 Rank distributions, not only their centers

A candidate with expected altitude 800 ft can still have a nonzero expected penalty.
It will sometimes fly above and sometimes below the target, and both misses cost
points.

For ballast $b$, the decision objective is:

$$
L(b)=\mathbb E\left[|Y_{\text{new}}(b)-H_\star|\right].
$$

The expectation means averaging the penalty over possible future outcomes,
weighted by their modeled probabilities.

For a simple invented example:

| Candidate | Possible outcomes, equally likely | Mean altitude | Expected altitude penalty |
| --- | --- | ---: | ---: |
| A | 780 or 820 ft | 800 ft | $(20+20)/2=20$ points |
| B | 794 or 814 ft | 804 ft | $(6+14)/2=10$ points |

Candidate B has lower expected penalty despite its mean being farther from
800 ft. This table illustrates expectation with a discrete distribution; the
program uses a continuous t distribution.

For the six-flight hand example at 530 g, the modeled expected altitude penalty
is about **2.716 points**, even though the corrected mean is exactly 800 ft.
The appendix gives the formula used to calculate this value.

Least squares is used to estimate the correction and its variability. Absolute
error is used to judge altitude decisions because that matches competition
scoring. Fitting and deciding are different jobs.

### 11.2 Understand the total mass sensitivity

Holding weather and base mass fixed, the local corrected sensitivity is:

$$
k=\frac{d\widehat Y}{dm}
=\frac{dS}{dm}+\widehat\beta_1.
$$

Estimate the OpenRocket term from nearby simulations under the same conditions:

$$
\frac{dS}{dm}\approx\frac{S(m+\Delta m)-S(m)}{\Delta m}.
$$

A small change intended to move the expected altitude toward the target is:

$$
\Delta b\approx\frac{H_\star-\widehat Y}{k}.
$$

In the hand example, OpenRocket changes from 860 ft at 520 g to 835 ft at 530 g:

$$
\frac{dS}{dm}\approx\frac{835-860}{10}=-2.5\text{ ft/g},
\qquad
k=-2.5-0.5=-3.0\text{ ft/g}.
$$

The corrected altitude at 520 g is $860-30=830$ ft. To reach 800 ft:

$$
\Delta b\approx\frac{800-830}{-3}=10\text{ g}.
$$

Adding 10 g gives the 530 g candidate already calculated.
Using only the correction slope of -0.5 ft/g would give the wrong answer.

This sensitivity is a local approximation, useful for choosing candidate
simulations. It becomes unreliable near a turning point where $k$ is near zero.
The implemented tool does not solve this derivative equation. It compares the
candidate simulations you supply and selects the eligible one with the lowest
modeled expected altitude penalty.

## 12. Design launches that teach us something

Keep geometry, surface finish, motor designation and delay, recovery setup,
ballast location, and preparation procedure consistent. Ballast amount is the
factor intentionally changed during mass calibration. Check the consequences
for CG, stability, and launch performance at each setting.

Repeats and mass variation answer different questions:

| Experiment | What it teaches |
| --- | --- |
| Repeat one ballast setting | Bias and flight-to-flight variation at that setting |
| Change ballast with no repeats | A possible mass response, mixed with unknown variation |
| Repeat several ballast settings | Mass response and repeatability |
| Repeat those settings across days | Whether the response generalizes across launch conditions |

Suppose all light flights occur on a cold day and all heavy flights on a warm day.
A trend with mass might actually be a day effect. Include all mass settings on
each calibration date and randomize their order within that date.
This uses [blocking and randomization](https://www.itl.nist.gov/div898/handbook/pri/section3/pri332.htm)
to reduce confounding. Matching weather in the simulator also helps, but does
not guarantee that every day effect has been removed.

The recommended initial practice budget in the [launch plan](README.md#launch-plan) is:

| Stage | Flights | Purpose |
| --- | ---: | --- |
| Same-setting baseline | 3 | Preliminary repeatability and operational checks |
| Three mass settings, three repeats each | 9 | Calibration across three launch dates |
| Later confirmation with the model frozen | 3 | Independent check of predictions |
| Total | 15 | Starting budget, expandable if needed |

Existing comparable baseline data can reduce the new-flight budget to 12.
Three baseline flights give a very uncertain estimate of scatter; three
confirmation flights cannot establish a precise 95% coverage rate.
The counts are planning choices, not universal statistical requirements.

Choose a mass spacing that produces altitude differences larger than the
preliminary scatter. If each of two settings has $q$ independent repeats and
the same noise standard deviation $\sigma$, then:

$$
\operatorname{SE}(\text{difference between two means})
=\sigma\sqrt{\frac2q}.
$$

For three repeats at each setting, this is about $0.816\sigma$.
A tiny mass effect can be difficult to distinguish from that uncertainty.
The launch plan's suggested altitude spacing of roughly two to three estimated
standard deviations is a starting heuristic, not a power guarantee.
The formula above assumes independent errors; correlated flights need more care.

## 13. How many launches are enough?

There is no fixed answer independent of the precision goal and observed variation.
Separate two goals:

1. Estimate average behavior precisely.
2. Make individual flights repeatable enough to score well.

For independent repeats at one fixed setting, a confidence interval for the mean is:

$$
\overline Y\pm t_{0.975,n-1}\frac{s}{\sqrt n}.
$$

This is a standard [t confidence interval for a mean](https://www.itl.nist.gov/div898/handbook/eda/section3/eda352.htm).

As a planning illustration, suppose the standard deviation is estimated to be
15 ft and we want a mean-altitude interval with half-width no more than 10 ft.
Holding that estimate fixed, try values of $n$ in:

$$
t_{0.975,n-1}\frac{15}{\sqrt n}\leq10.
$$

| Repeats at this fixed setting | Approximate mean-interval half-width |
| --- | ---: |
| 9 | 11.53 ft |
| 11 | 10.08 ft |
| 12 | 9.53 ft |

This suggests about 12 repeats for that particular mean-precision goal under
the assumptions. It is not a requirement for 12 launches at every ballast setting,
and it is not an exact sample-size guarantee because the true variation is unknown.
It also does not replace regression-based planning across several masses and days.

At $n=12$, the next-flight half-width at this same setting would be approximately:

$$
t_{0.975,11}\,15\sqrt{1+\frac1{12}}\approx34.36\text{ ft}.
$$

Knowing the mean within about 10 ft does not mean the next flight will be within
10 ft. Even with a very large dataset, genuine variation remains. If that
variation dominates the score, improve consistency rather than only collecting
more launches.

Before final confirmation, choose an altitude tolerance and an acceptable score.
For instance, +/-10 ft can be a team goal; it is not an ARC qualification tolerance.
Assess the individual-flight prediction interval and later prediction errors
against that goal. Do not stop solely because one flight reaches exactly 800 ft.

## 14. Check whether the model is believable

Inspect residuals after calibration, not only the fitted line or a training
goodness-of-fit number. [NIST discusses residual-based model checking](https://www.itl.nist.gov/div898/handbook/pmd/section4/pmd44.htm).

| Residual pattern | Possible interpretation | Useful next step |
| --- | --- | --- |
| No obvious trend, similar spread | Consistent with the simple model | Check independent confirmation |
| Trend with mass | Missing or incorrect mass correction | Add mass settings or reassess the correction |
| Curvature with mass | Linear correction may be too simple over this range | Narrow the range or collect evidence for a different model |
| Larger spread at high mass | Constant-variance assumption may fail | Add repeats and investigate the mechanism |
| Groups by launch date | Unmodeled weather or procedural effects | Compare within-date contrasts and validate on later dates |
| Trend with wind | Simulation may not capture trajectory differences adequately | Record wind direction and flight behavior; investigate |
| One extreme value | Data error, unusual event, or genuine tail behavior | Inspect the flight record; retain it unless exclusion is justified |

These are diagnostic hypotheses, not automatic explanations.
The tool currently does not draw residual plots or fit separate day effects.
Those are analysis steps to perform as the dataset grows.

Do not remove a flight simply because it makes a prediction look worse.
Record actual anomalies such as premature deployment, hardware damage, or a
sensor malfunction, and document whether they belong to the intended operating
population. A procedure that sometimes fails needs that reliability problem
addressed as well.

## 15. Know the limits of the evidence

The uncertainty calculation assumes:

- The chosen correction model is adequate over the predicted conditions.
- Remaining errors are independent and approximately normal with constant variance.
- The rocket configuration is unchanged.
- Each simulated altitude matches the flight's measured inputs.
- Proposed conditions are represented by the calibration data.

Real flight errors may violate these assumptions. Predictions do not automatically
include uncertainty from future weather, motor-batch changes, mass measurement
error, hidden within-day correlation, or choosing the model from the same dataset.

The program excludes recommendations outside the tested mass, ballast, and
recorded weather ranges, or above 650 g total launch mass. Passing separate
range checks does not prove that a new combination of inputs has been tested.
The program also cannot determine from those checks whether a rocket is stable,
has adequate rail-departure speed, or meets all competition requirements.

A numerical correction does not identify a physical cause:

$$
\text{too much drag},\quad
\text{less motor impulse},\quad
\text{a tilted trajectory}
\quad\Longrightarrow\quad
\text{a lower apogee can result}.
$$

One scalar apogee observation cannot generally distinguish all these mechanisms.
Altitude-versus-time data and additional measurements would help.

## 16. Reproduce the project's twelve-flight example

The repository contains a different synthetic dataset with twelve flights,
including four launch dates. It demonstrates the complete implemented workflow.

From the project directory, run:

~~~sh
uv run python -m rocket_calibration \
  --flights examples/synthetic_flights.csv \
  --candidates examples/synthetic_candidates.csv \
  --synthetic \
  --output outputs/synthetic_recommendation.json
~~~

Expected rounded results are:

| Output | Value |
| --- | ---: |
| Selected model | Linear correction |
| Reference launch mass | 520 g |
| Offset at reference mass | -30.1667 ft |
| Correction slope | -0.4000 ft/g |
| Residual standard deviation | 2.2286 ft |
| Degrees of freedom | 10 |
| Raw simulation MAE | 30.1667 ft |
| Offset model date-held-out MAE | 5.8519 ft |
| Linear model date-held-out MAE | 2.1852 ft |
| Recommended candidate | C30 |
| Recommended ballast | 30 g |
| Candidate total launch mass | 530 g |
| Candidate OpenRocket altitude | 832.5 ft |
| Corrected expected altitude | 798.3333 ft |
| Nominal 95% next-flight interval | 793.0909 to 803.5757 ft |
| Modeled expected altitude penalty | 2.4740 points |

For example:

$$
832.5-30.1667-0.4(530-520)=798.3333\text{ ft}.
$$

These are teaching results, not a recommendation for the real rocket.
Do not combine the numbers from this twelve-flight dataset with the six-flight
hand example. Their fitted parameters and uncertainty are different.

## 17. Map the equations to the code

| Concept | Program location |
| --- | --- |
| Validate CSV fields, units, IDs, and finite values | read_records() |
| Estimate the offset or linear correction with least squares | fit() |
| Evaluate the fitted correction at a launch mass | Calibration.correction() |
| Calculate corrected mean, predictive scale, and interval | Calibration.predict() |
| Compute held-out prediction MAE | validation() |
| Integrate the modeled absolute altitude penalty | expected_altitude_penalty() |
| Select a model, exclude candidates, and rank eligible candidates | analyze() |
| Compute altitude plus duration penalty for a measured flight | flight_score() |

The command-line workflow requires at least four measured flights.
A linear correction requires at least six flights, three distinct launch masses,
and estimable validation folds. These are implementation minimums.
They are not proof that an experiment has enough statistical information.

The program reads simulation apogees supplied in CSV files. It does not run
OpenRocket or directly read the design file. Its candidate choice is the best
among supplied eligible simulations; it is not a continuous optimum over all
possible ballast values.

## Appendix A. Derive the centered least-squares formulas

Minimize:

$$
Q=\sum_i(r_i-\beta_0-\beta_1x_i)^2,
\qquad
x_i=m_i-\overline m,
\qquad
\sum_i x_i=0.
$$

Set the derivative with respect to the intercept to zero:

$$
\frac{\partial Q}{\partial\beta_0}
=-2\sum_i(r_i-\beta_0-\beta_1x_i)=0.
$$

Therefore $n\beta_0=\sum_i r_i$, so $\widehat\beta_0=\overline r$.
For the slope:

$$
\frac{\partial Q}{\partial\beta_1}
=-2\sum_i x_i(r_i-\beta_0-\beta_1x_i)=0.
$$

Substitute the fitted intercept and rearrange:

$$
\widehat\beta_1\sum_i x_i^2
=\sum_i x_i(r_i-\overline r).
$$

Dividing by $\sum_i x_i^2>0$ gives the slope formula in section 6.

In matrix notation:

$$
\mathbf r=X\boldsymbol\beta+\boldsymbol\epsilon,
\qquad
X=
\begin{bmatrix}
1&m_1-\overline m\\
1&m_2-\overline m\\
\vdots&\vdots\\
1&m_n-\overline m
\end{bmatrix}.
$$

For full-rank $X$, the least-squares solution satisfies:

$$
\widehat{\boldsymbol\beta}=(X^\mathsf T X)^{-1}X^\mathsf T\mathbf r.
$$

This is a mathematical expression for the solution. The program estimates the
coefficients using a numerical least-squares solver rather than explicitly
inverting this matrix for the fit.

For a new design vector $\mathbf x=[1,\ m-\overline m]^\mathsf T$:

$$
\ell=\mathbf x^\mathsf T(X^\mathsf T X)^{-1}\mathbf x.
$$

Centering makes the off-diagonal terms of $X^\mathsf T X$ zero:

$$
X^\mathsf T X=
\begin{bmatrix}
n&0\\
0&S_{xx}
\end{bmatrix},
\qquad
\ell=\frac1n+\frac{(m-\overline m)^2}{S_{xx}}.
$$

The offset model uses a single column of ones and $\mathbf x=[1]$,
so its leverage is simply $1/n$.

## Appendix B. Expected absolute penalty under a t distribution

For decision ranking, the program uses the working predictive distribution:

$$
Y=\mu+aZ,
\qquad
Z\sim t_\nu,
$$

where $\mu$ is corrected predicted altitude, $a$ is predictive scale,
and $\nu$ is residual degrees of freedom.

Let:

$$
d=\mu-H_\star,
\qquad
z=\frac d a.
$$

Write $f_\nu$ for the standard t probability density and $F_\nu$ for its
cumulative distribution function. For $a>0$ and $\nu>1$:

$$
\boxed{
\mathbb E|Y-H_\star|
=d\left[2F_\nu(z)-1\right]
+2a\frac{\nu+z^2}{\nu-1}f_\nu(z)
}.
$$

To see where it comes from, split the integral for $|d+au|$ at $u=-d/a$,
where the expression inside the absolute value changes sign.
Use symmetry of the t distribution and the identity:

$$
\int_z^\infty u f_\nu(u)\,du
=\frac{\nu+z^2}{\nu-1}f_\nu(z).
$$

The first term reflects displacement from the target. The second reflects
uncertainty. Their combination is nonnegative even if $d<0$.

When $\mu=H_\star$, the first term vanishes:

$$
\mathbb E|Y-H_\star|
=2a\frac{\nu}{\nu-1}f_\nu(0).
$$

In our hand example, $\nu=4$ and $f_4(0)=3/8$, so:

$$
\mathbb E|Y-800|
=2a\frac43\frac38=a=2.715695\text{ points}.
$$

If the fitted scale is zero, the code returns $|\mu-H_\star|$ and separately
warns that near-zero residual variation does not establish real repeatability.

For fixed $a$, this symmetric distribution has its minimum expected absolute
penalty when $\mu=H_\star$. Across candidates, $a$ can change, which is why
looking only at the mean is incomplete.

## Practice questions

1. OpenRocket predicts 845 ft and a flight measures 812 ft. What is the
   discrepancy? If the estimated offset is this value and a new simulation is
   836 ft, what is the corrected prediction?
2. The ready-to-launch base mass, including motor and eggs but excluding
   adjustable ballast, is 500 g. You install 30 g of ballast. What total mass
   belongs in the simulation?
3. In the six-flight hand example, OpenRocket's local slope is -2.5 ft/g.
   Why is the corrected altitude sensitivity -3.0 ft/g rather than -0.5 ft/g?
4. The offset model has validation MAE 6.0 ft and the linear correction has
   validation MAE 5.5 ft. Which model does automatic selection prefer, assuming
   both have enough data?
5. A next-flight interval is 780 to 820 ft. The target is 800 ft and the team's
   tolerance is +/-10 ft. Does including 800 inside the interval establish that
   the desired precision has been achieved?
6. If the number of independent same-setting repeats increases by a factor of
   four while the estimated noise scale stays the same, how does the standard
   error of the mean change? Does the next-flight uncertainty go to zero?
7. All light flights were launched on one date and all heavy flights on another.
   What is the main interpretation problem?
8. Measured altitudes are consistently above 800 ft with a small spread, and
   the calibrated model predicts them accurately. What should be changed first?
   How would your answer differ if the average were correct but the spread large?

## Answer key

1. $812-845=-33$ ft. The new corrected prediction is $836-33=803$ ft.
2. $500+30=530$ g. Ballast is counted once.
3. The total response includes OpenRocket's slope plus the correction slope:
   $-2.5+(-0.5)=-3.0$ ft/g.
4. Offset. The improvement is $(6.0-5.5)/6.0=8.33\%$, less than the required
   10% project threshold. This threshold is not a significance level.
5. No. The interval extends outside the desired 790 to 810 ft band. Hitting
   the right center does not establish sufficient individual-flight precision.
6. The $s/\sqrt n$ standard error halves. The t critical value also changes
   slightly for a confidence interval. New flights still have their own variation,
   so next-flight uncertainty does not vanish.
7. Mass and launch date are confounded. Weather, procedures, or motor batches
   could explain an apparent mass effect. Test every setting within each date.
8. For a consistent target miss, use the calibrated response to adjust ballast, then
   confirm. For large spread with a correct average, investigate repeatability
   before reacting to each altitude miss. More fitting alone does not remove
   physical variation.
