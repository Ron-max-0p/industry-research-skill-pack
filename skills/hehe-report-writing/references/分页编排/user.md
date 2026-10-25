# User Mode

Use for 用研模块脚本, including pure survey-analysis-to-script tasks.

This mode replaces the old standalone survey-report helper dependency. When the input is mainly a survey analysis workbook and Excel chart library, write the survey report script directly here.

## Inputs

Preferred inputs:
- project control file;
- 用研状态卡;
- questionnaire design package;
- interview guide and notes;
- survey analysis workbook;
- survey chart library;
- public platform feedback;
- user segmentation or persona notes;
- legacy survey page scripts if available.

## Survey-Heavy Tasks

When the task is based on questionnaire data, include a visible mapping chain:

`question / variable -> frequency or cross table -> chart -> page conclusion -> boundary`

For every survey-driven page, specify:

- source question number, variable name, sheet, or chart-library block;
- analysis type: frequency, multi-select percentage, mean score, TOP2, cross-tab, significance test, segmentation, funnel, Kano, NPS, price test, or open-end coding;
- chart type and whether the chart already exists in the chart library;
- Base, skip logic, quota, weighting, and small-sample boundary;
- whether the conclusion is descriptive, comparative, directional, or statistically supported;
- whether the page needs rerun, chart-library adjustment, or F confirmation.

Do not organize the report as a questionnaire dump. The chart library may follow question order; the report script must reorganize evidence around decisions, user segments, behavior chains, pain points, product value, pricing, or strategic implications.

## Page Types

| Page type | Purpose |
|---|---|
| 样本与方法页 | State sample, base, and method boundary |
| 用户分层页 | Explain who is being compared |
| 行为链路页 | Show actual behavior before attitudes |
| 需求/痛点页 | Show pain strength and scenarios |
| 动因/阻碍页 | Explain adoption or rejection |
| 功能/卖点页 | Connect product features to user value |
| 价格/付费页 | Show acceptance and sensitivity |
| 访谈洞察页 | Add qualitative mechanism or story |
| 用户小结页 | Hand off to strategy or integrated report |

## Evidence Rules

- Separate existing users and potential users unless F总 confirms a combined view.
- Every survey chart must state Base and sample boundary.
- Qualitative interviews explain mechanism; they do not prove population size.
- Public platform feedback is directional, not representative.
- Non-significant differences must not be written as clear leads.

## Required Output Emphasis

Include:
- method boundary;
- sample split;
- key charts and bases;
- quote or qualitative evidence only when useful;
- what must be rerun or cross-tabbed;
- what should not enter PPT.

## Common P0 Blockers

- target sample not confirmed;
- questionnaire path unclear;
- missing Base for key page;
- existing and potential users mixed without logic;
- price conclusion without price-test evidence.
