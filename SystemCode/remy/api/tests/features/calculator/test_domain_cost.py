from api.features.calculator.domain.cost import consumed_cost, round_money, select_package
from api.features.calculator.models import RetailSKU


def test_selects_lowest_price_per_gram_and_covers_amount():
    packages = [
        RetailSKU("A", "small", 100, "SGD", 100, 1, "package_mass", True, fdc_id="2"),
        RetailSKU("B", "large", 250, "SGD", 500, 1, "package_mass", True, fdc_id="1"),
    ]
    chosen = select_package(packages, 150)
    assert chosen[0].retailer == "B"
    assert chosen[1] == 1
    assert round_money(consumed_cost(chosen[0], 150)) == 0.75
