# ROSA2018 complete system plan

Date: 10 September 2026

Status: Proposed architecture and build plan. This document does not report implemented software or validated scientific performance.

The user can give ROSA a broad goal, such as finding interventions that could prevent or reverse Alzheimer's disease. ROSA must select the research scope, divide the goal into testable questions, select actions, receive results, and revise its programme. The user does not have to select the first phenotype, cell type, or mechanism.

The scientific objective remains broad. Each calculation, prediction, and experiment has a precise scope. A bounded engine means that the software declares which inference methods it can execute and validate. It does not mean that the user must restrict the entire disease programme to one permanent question.

All recommendations below are design proposals. The underlying methods do not establish that the combined ROSA system will succeed.

## 1. Broad goal to research programme

Use a persistent hierarchy:

Programme goal → research areas → campaigns → questions → hypotheses → actions → observations → revised questions and actions.

A programme charter records the disease goal, available resources, allowed actions, laboratory capabilities, and decision authority. ROSA proposes visible defaults where values are absent. It can start low-cost research with incomplete resource information. It must not treat an unknown resource as available or an unknown permission as granted.

ROSA builds an initial disease map from reviewed sources. The map includes disease stages, populations, cell and tissue contexts, measured outcomes, possible mechanisms, existing interventions, conflicting findings, and evidence gaps. It records search limits. It does not claim complete coverage of the disease.

A research planner proposes several research areas. It compares disease relevance, possible intervention value, uncertainty, testability, cost, delay, and dependence on other work. It retains different mechanism families and records areas that remain unexplored. Data availability is one selection factor; it must not become a substitute for relevance to the disease goal.

For each selected campaign, ROSA creates the specific question. The question contains the population or experimental context, intervention, comparator, outcome, time window, independent biological unit, and decision to be made. ROSA proposes a meaningful effect threshold from the scientific objective and assay capability. It records an unresolved threshold if no defensible value is available.

Illustrative question template, not a biological claim: In context C and stage S, does intervention A change outcome P over time T relative to comparator B, and can the experiment distinguish mechanism M1 from M2?

Each campaign has a path back to the programme goal. The path distinguishes target engagement, mechanism change, functional outcome, practical intervention, and evidence of benefit in the intended population. Biomarker changes cannot silently replace the programme objective.

The planner revisits campaign allocation when results, costs, methods, or available resources change. It can reopen a paused area. An unknown mechanism remains a permitted explanation.

## 2. Recommended causal engine

Use three cooperating components.

1. A typed rule engine checks evidence fields, source status, context compatibility, prerequisites, and permitted conclusions. Use Datalog-style rules with explicit unknown states. Absence of a record does not establish a negative fact.
2. A structural causal model component represents candidate mechanisms, interventions, possible unmeasured causes, and time. It checks whether the requested effect can be determined from the model assumptions and available evidence. It can return a bound or an unresolved result.
3. Statistical components estimate effects and uncertainty. Use a suitable model for each design. Use hierarchical models when evidence can be combined and its dependence can be represented. Use sensitivity analysis when conclusions depend on uncertain assumptions.

Keep observed evidence, proposed causal models, and operational decisions as separate records. A causal edge can be an explicit assumption or an evidence-supported inference. The system must display this distinction.

Begin with controlled intervention contrasts, simple mediation questions with declared assumptions, and limited context-transfer questions. Add other methods as independently tested modules. Represent feedback through time-indexed variables or a suitable dynamic model. Do not force all biological feedback into a static graph.

Every supported query returns the requested causal quantity, the assumptions, the source evidence, the method, the estimated effect or permitted conclusion, the uncertainty, and the remaining limits. Unsupported queries produce a reason and a possible route to further evidence.

Do not use one scalar score as causal truth. Keep effect uncertainty, evidence quality, context applicability, scientific support, feasibility, and priority separate. A mechanism can have scientific support and low practical priority.

Do not convert repeated associations into causation by adding weights. Do not assume that intervention A changes only target X. Do not join two causal links from incompatible contexts without a stated transfer argument.

Source basis: Pearl and Bareinboim, External Validity: From Do-Calculus to Transportability Across Populations, https://ftp.cs.ucla.edu/pub/stat_ser/r400-reprint.pdf. The paper supports explicit causal assumptions and transfer conditions. It does not validate ROSA.

## 3. Source text to checked evidence

Use this sequence:

Source file → source location → extracted observation → normalized record → automated checks → review where required → accepted evidence version.

An LLM can propose records. It must retain the passage, table, figure, or data artifact that supports each field. Another LLM can help check the extraction, but agreement between models is not independent scientific evidence.

Separate measurements, analysis results, author interpretations, and ROSA interpretations. A conclusion in a discussion section must not become a measured result.

Each evidence record includes:

- Source identifier, location, version, file hash, access conditions, and correction status.
- Study, cohort, donor, sample, and analysis identifiers where available.
- Variables, biological entities, measurement level, units, and assay.
- Context, disease stage, intervention, comparator, dose, and time.
- Controls, independent sample count, effect estimate, and uncertainty.
- Target engagement and intervention specificity where relevant.
- Known dependence on other records, limitations, and unresolved fields.
- Extraction version, review status, and linked assumptions.

Automated checks detect unit conflicts, reversed effect direction, missing comparator information, inconsistent sample counts, duplicate source data, and unsupported field values. They cannot establish facts that the source does not report.

Initially, a qualified reviewer checks every record that can change a major scientific decision. After extraction performance is measured, use review rules based on the consequence of error and the measured error rate. Preserve disagreements.

Build two evaluation sets: human-reviewed records to test the inference engine, and raw source packets to test the complete extraction path. Track whether an error came from retrieval, extraction, normalization, analysis, or inference.

## 4. Result-to-next-decision cycle

Use an event record for every scientific action. An action is a literature query, data request, computation, measurement, experiment, or review. Every event links to the exact question, hypothesis, method, inputs, and decision version.

Before an experiment, register the predictions, primary outcome, controls, analysis method, and decision criteria. For adaptive work, register the permitted adaptation rules or create a dated amendment before the affected results are examined.

After execution:

1. Import the actual protocol, raw results, and execution deviations.
2. Confirm the experiment and sample identities.
3. Check technical quality and intervention success.
4. Run the specified analysis and retain its artifacts.
5. Determine which predictions and assumptions the result can test.
6. Update every affected hypothesis in its applicable context.
7. Recompute affected action priorities and campaign allocation.
8. Record the next decision, its reason, and unresolved objections.

Keep technical failure, inconclusive measurement, interpretable small effect, predicted effect, unexpected effect, and toxicity as distinct dimensions where they can coexist. Do not force every result into one positive or negative label.

Pending results remain part of the planning state. A late result updates the hypothesis version it actually tested, then triggers a compatibility check against current versions. The software must prevent duplicate imports and duplicate execution after a restart.

The laboratory retains responsibility for physical execution. ROSA prepares requests and receives results through agreed interfaces. Actions within an approved operational scope can proceed without repeated review. New experimental commitments follow the assigned approval rules.

## 5. Searchable method and test registry

Register analysis methods, predictors, data resources, and laboratory assays. Each entry states:

- The claim or outcome it can assess.
- Applicable biological contexts and known exclusions.
- Required inputs, units, controls, sample design, and output format.
- Available validation evidence, reference comparisons, uncertainty, and known failures.
- Software, protocol, and training-data versions where applicable.
- Dependence on other methods or source data.
- Cost, duration, capacity, material requirements, and responsible operator.
- Current status: proposed, implemented, tested in specified contexts, restricted, or retired.

Search combines structured filters with semantic retrieval. First find methods compatible with the question and available resources. Then compare expected decision value. A method's popularity or citation count cannot establish suitability.

When no suitable method exists, ROSA creates an assay-development, calibration, or data-acquisition task. It may also pause the question with a stated reason.

A predictor contributes predicted evidence. It cannot produce independent confirmation of its own training data. Experimental results update its measured reliability within the relevant domain, with selection bias and sample size stated.

## 6. Decision objective and stopping rules

Use expected improvement in the research decision as the main objective. The available actions include further search, reanalysis, assay qualification, experiment, replication, waiting, revision, and stopping.

When probabilities and utilities are defensible, estimate the expected benefit of the best decision after a result, relative to the best decision with current evidence. Account for cost, delay, required materials, and the remaining programme budget. State the assumptions and test how sensitive the ranking is to them.

Information gain is useful when the decision concerns which mechanism to investigate. It is not automatically equivalent to treatment value. A test that separates two mechanisms may have low decision value if both imply the same next action.

When quantitative inputs are weak, retain a transparent comparison of relevance, interpretability, uncertainty reduction, cost, and delay. Show competing options rather than a false probability of success.

For batches, consider shared controls, shared setup costs, redundant information, and pending results. Allocate part of the available effort to alternative mechanism families and to tests of uncertain assumptions. Set the allocation through explicit policy and evaluate it; do not present an arbitrary percentage as scientifically optimal.

Define separate stop conditions for an individual test, a hypothesis, a campaign, and the programme. Examples include sufficient evidence for the current decision, a prediction contradicted within its tested scope, an invalid assay, no useful available action, and an exhausted resource limit. Paused campaigns retain conditions for reopening.

Source basis: Rainforth and colleagues, Modern Bayesian Experimental Design, https://arxiv.org/html/2302.14545v2. The framework supports explicit experiment models and utilities. The ROSA objective and implementation require their own evaluation.

## 7. Independent evaluation of added value

Evaluate the research planner as well as the hypothesis engine. Give comparison systems the same broad goal, starting evidence, method access, and total resource limits. Include human review time in cost.

Use these comparison conditions:

- A scientist using the current research process.
- A scientist with an LLM and evidence retrieval.
- ROSA with fixed evidence but selected components disabled for a controlled comparison.
- The complete ROSA configuration.

For component comparisons, hold the relevant upstream inputs fixed. For whole-system comparisons, let question selection differ and evaluate the resulting programme against the same broad goal.

Test at five levels:

1. Synthetic cases with known causal structures. Test inference rules, unknown states, dependence, and wrong model assumptions.
2. Real source extraction with independent review. Include conflicting studies, missing fields, corrected papers, and reused cohorts.
3. Historical result replay. Release only the evidence available at each decision point. Report pretraining contamination limits and unmeasured alternative actions.
4. Prospective laboratory campaigns. Register predictions and outcome criteria before new measurements. Compare policies across enough independent campaigns to support the intended claim.
5. Researcher use. Measure review time, correction burden, actionability, and the ability to reconstruct and challenge decisions.

Primary measures include unsupported causal claims, correct uncertainty handling, useful decisions, prediction performance, interpretable experiments, total cost, elapsed time, and reviewer effort. Measure missed valid candidates only where an independent assessment is possible. Report the denominator and uncertainty for every rate.

Include cases that require advancement and cases that require abstention. Rejecting everything must not produce a good score. A visually clear report is not an independent scientific success measure.

Do not evaluate ROSA only with the predictor or simulator used to guide it. Historical replay cannot reveal the outcome of an experiment that was never measured. Record such cases as unevaluable or simulated.

## 8. Shared learning from failed and successful work

Store observations in a shared evidence store. Link them to all compatible claims and hypotheses. A hypothesis owns its prediction and interpretation; it does not exclusively own the observation.

When a prediction fails, ROSA examines the intervention, assay, measurement sensitivity, model assumptions, and biological context. It proposes new measurements that can distinguish these explanations. It must not repeatedly revise assumptions merely to preserve a preferred mechanism.

An illustrative result: intervention A engages X and changes Y, but does not change phenotype P within informative limits. This result can support an A-to-Y effect and weaken the prediction that this intervention changes P. It does not by itself prove that Y is unrelated to P or validate a competing mechanism.

A failed assay can inform method reliability, resource estimates, or protocol changes. It does not automatically provide evidence against the biological mechanism. Its other measurements remain usable only if their own quality checks pass.

Reopen a hypothesis only when new evidence, a corrected record, a changed context, or a newly suitable method addresses its previous stopping reason. Keep its earlier prediction and outcome. New hypotheses formed from a result require new tests for confirmation.

Learn at three separate levels: update evidence and scientific support; propose changes to planning or method selection; propose changes to software, prompts, or model weights. The latter changes require reserved evaluation and controlled promotion. Evidence updates need not wait for model retraining.

## 9. Automatic correction and dependency tracking

Use immutable source and result versions, plus a dependency graph from evidence to analyses, claims, hypotheses, decisions, and reports.

When a source, extraction, method, or rule changes:

1. Identify dependent outputs.
2. Mark affected conclusions as requiring recomputation or review.
3. Recompute permitted outputs from the new version.
4. Produce a decision difference report with old and new support.
5. Reassess pending work and notify its responsible reviewers when the change matters.

Automatic recomputation does not provide authority to start or cancel physical work outside the existing authorization. Keep an explicit state for affected experiments already in progress.

Preserve the record of what ROSA knew when it made each decision. A historical report remains a historical report; it must not silently acquire current conclusions.

## 10. Complete technical architecture

Use a modular application with one authoritative state store before dividing the system into multiple services. A transactional database stores records and decisions. Immutable file storage holds source files, data, and results. Search indexes are derived views that can be rebuilt.

The main modules are the programme planner, source acquisition service, evidence processing service, causal engine, hypothesis generator and critic, method registry, action planner, numerical execution service, laboratory interface, dependency updater, evaluation service, and researcher interface.

Core records are Programme, Campaign, Question, Source, Observation, AnalysisResult, EvidenceClaim, Assumption, CausalModel, HypothesisVersion, MethodVersion, ActionPlan, Run, LabOutcome, Decision, Evaluation, and ChangeProposal. Every record has stable identity, version, source links, and status.

The researcher interface must show the broad goal, active campaigns, reasons for scope selection, supporting and conflicting evidence, pending results, budget use, and decisions requiring review. It must allow a researcher to inspect a conclusion back to its measurements and assumptions.

The execution service enforces action permissions, resource limits, frozen criteria, retries, and artifact checks. It records real execution status and isolates executable work. Retrieved documents are evidence, not system instructions.

The therapeutic development path must remain explicit: mechanism → intervention options → target engagement → functional effect → selectivity and toxicity → delivery and exposure → independent replication → evidence relevant to the intended population. ROSA can propose tasks at each step. A completed cellular campaign does not complete this entire path.

## 11. Build sequence and release gates

The MVP is the first demonstrator within this plan. It does not replace the complete architecture.

| Stage | Delivered capability | Exit evidence |
|---|---|---|
| A. System contract | Programme hierarchy, record formats, inference boundaries, permissions, and evaluation protocol | Reviewed examples with expected decisions and assigned owners |
| B. Evidence and causal core | Source checking, typed claims, limited causal methods, numerical execution, dependency tracking | Extraction checks, relevant reproductions, inference tests, and correction tests |
| C. First complete cycle | ROSA selects a narrow question from a broad goal, chooses an action, imports results, and selects another action | A reconstructable cycle with real evidence and clearly labelled replay or simulated feedback |
| D. Adaptive programme | Multiple campaigns, scope revision, shared evidence, method selection, pending results, and budget allocation | Fixed-budget comparisons and recovery from unexpected evidence |
| E. Laboratory operation | Agreed experiment requests, actual-protocol intake, sample identity, quality checks, and consequential decision review | Prospective campaigns with registered predictions and complete outcome reporting |
| F. Scientific evaluation | Independent comparisons against simpler research processes | Reported effects, uncertainty, costs, failures, and limits of generalization |
| G. Expansion and sustained operation | More scientific methods, contexts, intervention classes, controlled learning, and reliable operation | Each extension passes its own evidence, method, and operational checks |

Retain the ROSA2018 three-analysis reproduction requirement for the release to which it applies. One reproduction can be an earlier component milestone. Record any change to the release requirement explicitly.

Do not assign a completion date to the full system from the October demonstrator date alone. Estimate stage durations after data access, staff availability, supported methods, and laboratory turnaround are confirmed. Track computational, data-access, scientific-review, and experimental dependencies separately.

## 12. People, resources, and acceptance

Assign a programme sponsor, a scientific lead, a causal/statistical methods lead, a data and bioinformatics lead, an engineering owner, a laboratory owner, and an independent evaluation owner. Some roles can be combined, but the author of a scientific conclusion must not be its only evaluator.

The sponsor sets programme priorities and resource authority. The scientific lead approves scientific criteria and major interpretation decisions. Method specialists own validation domains. Engineering owns execution and record integrity. The laboratory owns physical protocols and quality. Evaluation owns reserved tests and comparison procedures.

Budget staff time, reviewer time, source access, storage, computation, model calls, assay development, experiments, and replication. Record both total limits and per-action limits. Maintain explicit fallback plans for unavailable data or methods without substituting irrelevant evidence.

Accept engineering and science separately. Engineering acceptance demonstrates correct records, execution, recovery, permissions, updates, and usable interfaces. Scientific acceptance applies only to the evaluated tasks, methods, contexts, and decision claims.

## 13. Source and decision record

This plan incorporates the user's clarification on 10 September 2026: ROSA creates the research scope from a broad disease goal; results can update any compatible work; rejected hypotheses remain recoverable; and the complete system plan is separate from its MVP.

Project sources reviewed in the preceding project analysis: PromptROSA.rtf; ROSA2018_Proyecto_Concepto_End_to_End_v1_0.docx; the ROSA concept, document analysis, paper review, and MVP tasks; and Closing the Loop in AI-Driven Biomedical Discovery, supplied preprint version 1, DOI 10.20944/preprints202608.2107.v1.

The preprint supplies design arguments about repeated research cycles. It does not establish the validity of this proposed implementation. The source documents are proposals, and no implementation evidence was found in the local ROSA folder during the review.
