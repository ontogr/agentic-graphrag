"""Graph schema for the Financial benchmark corpus.

Covers SEC filings and earnings releases. Numbers are modeled only for headline line
items, each with a value, unit, scale and period. Periods and filings are entities
because questions name a company and a period but not the document.
"""

from agrag.common.data_models.graph_schema import EntityType, GraphSchema, RelationType


FINANCIAL = GraphSchema(
    name="financial",
    version="1",
    entities=[
        EntityType(
            label="Company",
            description=(
                "The reporting company of a filing, under its legal name or common "
                "short name (for example Boeing, The Boeing Company)."
            ),
            properties={"ticker": "str", "sector": "str"},
        ),
        EntityType(
            label="Filing",
            description=(
                "One filed document: a 10-K, 10-Q, 8-K or earnings release, named by "
                "its cover page."
            ),
            properties={"form_type": "str", "fiscal_year": "str", "period_end": "date"},
        ),
        EntityType(
            label="FiscalPeriod",
            description=(
                "A fiscal year or quarter as the company labels it, such as FY2022 or "
                "the fourth quarter of fiscal 2022."
            ),
            properties={"period_kind": "str", "period_end": "date"},
        ),
        EntityType(
            label="FinancialMetric",
            description=(
                "A headline reported figure: revenue, cost of sales, gross profit, "
                "operating income, net income, earnings per share, total assets, "
                "current liabilities, total liabilities, equity, accounts payable, "
                "operating, investing or financing cash flow, capital expenditure, or "
                "an effective tax rate. Do not extract other table line items."
            ),
            properties={
                "metric_name": "str",
                "value": "float",
                "unit": "str",
                "scale": "str",
                "currency": "str",
            },
        ),
        EntityType(
            label="BusinessSegment",
            description=(
                "A reportable segment, division or product category of a company."
            ),
        ),
        EntityType(
            label="Product",
            description="A named product, service line or aircraft or vehicle program.",
        ),
        EntityType(
            label="Organization",
            description=(
                "A named organization other than the reporting company: a subsidiary, "
                "customer, supplier, competitor, lender, regulator or counterparty."
            ),
        ),
        EntityType(
            label="Person",
            description="A named executive, director or other individual.",
            properties={"title": "str"},
        ),
        EntityType(
            label="Risk",
            description=(
                "A stated risk factor or business exposure, such as cyclicality."
            ),
            properties={"description": "str"},
        ),
        EntityType(
            label="LegalProceeding",
            description="A lawsuit, investigation, claim or regulatory action.",
            properties={"status": "str", "description": "str"},
        ),
        EntityType(
            label="Guidance",
            description=(
                "A forward-looking statement, outlook or forecast the company gives."
            ),
            properties={"description": "str"},
        ),
        EntityType(
            label="Event",
            description=(
                "A dated corporate event such "
                "as an acquisition, divestiture or restructuring."
            ),
            properties={"event_type": "str", "description": "str"},
        ),
        EntityType(
            label="FilingSection",
            description=(
                "A named part of a filing, such as Item 7, Item 3 or Note 21, that the "
                "text cites or that holds a fact."
            ),
            properties={"section_id": "str"},
        ),
    ],
    relations=[
        RelationType(
            label="FILED",
            description="A company filed a document.",
            patterns=[("Company", "Filing")],
        ),
        RelationType(
            label="REPORTS_PERIOD",
            description="A filing reports results for a period.",
            patterns=[("Filing", "FiscalPeriod")],
        ),
        RelationType(
            label="REPORTED_METRIC",
            description="A company reported a figure.",
            patterns=[("Company", "FinancialMetric")],
        ),
        RelationType(
            label="FOR_PERIOD",
            description="A figure or forecast applies to a period.",
            patterns=[
                ("FinancialMetric", "FiscalPeriod"),
                ("Guidance", "FiscalPeriod"),
            ],
        ),
        RelationType(
            label="FOR_SEGMENT",
            description="A figure applies to one segment.",
            patterns=[("FinancialMetric", "BusinessSegment")],
        ),
        RelationType(
            label="HAS_SEGMENT",
            description="A company reports a segment.",
            patterns=[("Company", "BusinessSegment")],
        ),
        RelationType(
            label="OFFERS",
            description="A company or segment sells a product.",
            patterns=[("Company", "Product"), ("BusinessSegment", "Product")],
        ),
        RelationType(
            label="OFFICER_OF",
            description="A person serves as an officer or director of a company.",
            patterns=[("Person", "Company")],
        ),
        RelationType(
            label="SUBSIDIARY_OF",
            description="An organization is owned by a company.",
            patterns=[("Organization", "Company")],
        ),
        RelationType(
            label="CUSTOMER_OF",
            description="An organization buys from a company.",
            patterns=[("Organization", "Company")],
        ),
        RelationType(
            label="SUPPLIER_OF",
            description="An organization sells to a company.",
            patterns=[("Organization", "Company")],
        ),
        RelationType(
            label="COMPETES_WITH",
            description="An organization competes with a company.",
            patterns=[("Organization", "Company")],
        ),
        RelationType(
            label="LENDER_TO",
            description="An organization lends to a company.",
            patterns=[("Organization", "Company")],
        ),
        RelationType(
            label="FACES_RISK",
            description="A company or segment is exposed to a risk.",
            patterns=[("Company", "Risk"), ("BusinessSegment", "Risk")],
        ),
        RelationType(
            label="INVOLVED_IN",
            description="A company or organization is a party to a proceeding.",
            patterns=[
                ("Company", "LegalProceeding"),
                ("Organization", "LegalProceeding"),
            ],
        ),
        RelationType(
            label="GIVES_GUIDANCE",
            description="A company issues a forecast or outlook.",
            patterns=[("Company", "Guidance")],
        ),
        RelationType(
            label="ACQUIRED",
            description="A company bought another company or organization.",
            patterns=[("Company", "Organization"), ("Company", "Company")],
        ),
        RelationType(
            label="HAS_EVENT",
            description="A company took part in an event.",
            patterns=[("Company", "Event")],
        ),
        RelationType(
            label="OCCURRED_IN",
            description="An event took place in a period.",
            patterns=[("Event", "FiscalPeriod")],
        ),
        RelationType(
            label="CONTAINS_SECTION",
            description="A filing contains a named section.",
            patterns=[("Filing", "FilingSection")],
        ),
        RelationType(
            label="REFERS_TO",
            description="A section points to another section.",
            patterns=[("FilingSection", "FilingSection")],
        ),
        RelationType(
            label="DISCLOSED_IN",
            description="A figure, risk or proceeding is described in a section.",
            patterns=[
                ("FinancialMetric", "FilingSection"),
                ("Risk", "FilingSection"),
                ("LegalProceeding", "FilingSection"),
            ],
        ),
    ],
)
