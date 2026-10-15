import math
from decimal import Decimal, ROUND_HALF_UP
from ..models import RetailSKU


def package_price(package: RetailSKU) -> float | None:
    if package.currency != "SGD" or package.reference_price_minor is None or package.reference_price_minor <= 0:
        return None
    return package.reference_price_minor / 100.0


def select_package(packages: list[RetailSKU], grams: float) -> tuple[RetailSKU, int, float] | None:
    choices = []
    for package in packages:
        price = package_price(package)
        if (package.price_basis != "package_mass" or package.cost_basis_compatible is not True or
                package.package_mass_g is None or package.package_mass_g <= 0 or price is None):
            continue
        count = max(1, math.ceil(grams / package.package_mass_g))
        choices.append((price / package.package_mass_g, count * price, -(package.confidence or 0),
                        package.fdc_id, package.retailer or "", package.listing_name or "", package, count, price))
    if not choices:
        return None
    chosen = min(choices, key=lambda x: x[:6])
    return chosen[6], chosen[7], chosen[8]


def consumed_cost(package: RetailSKU, grams: float) -> float | None:
    price = package_price(package)
    if price is None or not package.package_mass_g or package.package_mass_g <= 0:
        return None
    return price * grams / package.package_mass_g


def round_money(value: float | None) -> float | None:
    if value is None:
        return None
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def round_nutrient(key: str, value: float | None) -> float | None:
    if value is None:
        return None
    quantum = Decimal("1") if key == "sodium_mg" else Decimal("0.01")
    return float(Decimal(str(value)).quantize(quantum, rounding=ROUND_HALF_UP))
