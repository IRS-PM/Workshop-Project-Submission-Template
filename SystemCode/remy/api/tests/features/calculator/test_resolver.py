from api.features.calculator.resolver import normalize_name, resolve, search_terms, singular_forms


def test_normalization_and_alias():
    assert normalize_name("  Crème--Brûlée! ") == "creme brulee"
    assert resolve("oatmeal", ["rolled oats"])[0] == "rolled oats"


def test_aliases_match_plural_names_and_keys():
    assert resolve("Chicken Fillets", ["chicken breasts"]) == ("chicken breasts", "alias", 1.0)
    assert resolve("oatmeal", ["Rolled Oats", "oat milk"])[:2] == ("Rolled Oats", "alias")


def test_exact_match_wins():
    assert resolve("Chicken Breast", ["chicken breast", "chicken"])[1] == "exact"


def test_singular_forms_include_the_pipeline_spellings():
    assert singular_forms("Tomatoes") == ["tomato", "tomatoe"]
    assert singular_forms("Bay Leaves") == ["bay leaf", "bay leave"]
    assert singular_forms("bay leaf") == ["bay leaf", "bay leave"]
    assert singular_forms("chilies") == ["chili", "chily"]
    assert singular_forms("Eggs") == ["egg", "eggs"]
    assert singular_forms(" !! ") == []


def test_search_terms_add_the_alias_forms():
    assert search_terms("Oatmeal") == ["oatmeal", "rolled oat", "rolled oats"]


def test_plural_names_resolve_to_pipeline_keys():
    assert resolve("Bay Leaves", ["bay leave", "bay leaf powder"])[:2] == ("bay leave", "exact")
    assert resolve("tomato", ["cherry tomatoe", "tomatoe"])[:2] == ("tomatoe", "exact")
    assert resolve("tomatoes", ["tomato", "tomatoe"])[:2] == ("tomato", "exact")
