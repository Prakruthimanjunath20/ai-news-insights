"""Reference data: the UK-listed companies, sectors and regulators the engine knows about.

Kept as plain Python so it is easy to read, review and extend.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Company:
    ticker: str
    name: str
    sector: str
    aliases: tuple[str, ...] = ()

    @property
    def all_names(self) -> tuple[str, ...]:
        return (self.name, *self.aliases)


@dataclass(frozen=True)
class Sector:
    name: str
    keywords: tuple[str, ...]


@dataclass(frozen=True)
class Regulator:
    name: str
    aliases: tuple[str, ...]
    affects_sectors: tuple[str, ...] = field(default_factory=tuple)


# fmt: off
SECTORS: tuple[Sector, ...] = (
    Sector(
        "Banking",
        (
            "bank", "banks", "banking", "lender", "lenders", "mortgage", "mortgages",
            "interest rate", "interest rates", "rate cut", "rate rise",
        ),
    ),
    Sector("Energy", ("oil", "gas", "energy", "crude", "brent", "refinery", "refining")),
    Sector(
        "Pharmaceuticals",
        ("pharma", "pharmaceutical", "drug", "drugs", "drugmaker", "drugmakers", "vaccine"),
    ),
    Sector(
        "Retail",
        ("retail", "retailer", "retailers", "supermarket", "supermarkets", "grocer", "grocery"),
    ),
    Sector("Telecoms", ("telecom", "telecoms", "broadband", "mobile network", "5g")),
    Sector(
        "Aerospace & Defence",
        ("aerospace", "defence", "defense", "jet engine", "jet engines", "aircraft"),
    ),
    Sector("Consumer Goods", ("consumer goods", "household brands")),
)
# fmt: on

COMPANIES: tuple[Company, ...] = (
    Company("HSBA", "HSBC Holdings", "Banking", ("HSBC",)),
    Company("BARC", "Barclays", "Banking"),
    Company("LLOY", "Lloyds Banking Group", "Banking", ("Lloyds", "Lloyds Bank")),
    Company("NWG", "NatWest Group", "Banking", ("NatWest",)),
    Company("BP", "BP", "Energy"),
    Company("SHEL", "Shell", "Energy"),
    Company("AZN", "AstraZeneca", "Pharmaceuticals"),
    Company("GSK", "GSK", "Pharmaceuticals"),
    Company("TSCO", "Tesco", "Retail"),
    Company("SBRY", "Sainsbury's", "Retail", ("Sainsbury",)),
    Company("VOD", "Vodafone", "Telecoms"),
    Company("BT.A", "BT Group", "Telecoms", ("BT",)),
    Company("RR", "Rolls-Royce", "Aerospace & Defence", ("Rolls Royce",)),
    Company("BA", "BAE Systems", "Aerospace & Defence", ("BAE",)),
    Company("ULVR", "Unilever", "Consumer Goods"),
)

REGULATORS: tuple[Regulator, ...] = (
    Regulator(
        "Bank of England",
        ("Bank of England", "BoE", "Monetary Policy Committee", "MPC"),
        ("Banking",),
    ),
    Regulator("FCA", ("Financial Conduct Authority", "FCA"), ("Banking",)),
    Regulator("PRA", ("Prudential Regulation Authority", "PRA"), ("Banking",)),
    Regulator("Ofgem", ("Ofgem",), ("Energy",)),
    Regulator("Ofcom", ("Ofcom",), ("Telecoms",)),
    Regulator(
        "MHRA",
        ("MHRA", "Medicines and Healthcare products Regulatory Agency"),
        ("Pharmaceuticals",),
    ),
    Regulator("CMA", ("Competition and Markets Authority", "CMA"), ()),
)


_BY_TICKER = {c.ticker: c for c in COMPANIES}


def company_by_ticker(ticker: str) -> Company | None:
    return _BY_TICKER.get(ticker.upper())


def companies_in_sector(sector: str) -> list[Company]:
    return [c for c in COMPANIES if c.sector == sector]


def regulator_by_name(name: str) -> Regulator | None:
    return next((r for r in REGULATORS if r.name == name), None)
