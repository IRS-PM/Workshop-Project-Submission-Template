from api.features.calculator.models import FoodFacts, NutrientProfile
from api.features.calculator.schemas import CostNutritionRequest
from api.features.calculator.service import CostNutritionService


class FakeRepository:
    def __init__(self, keys):
        self.keys = keys
        self.searched = None

    def resolve_candidates(self, terms):
        self.searched = terms
        return {term: [key for key in self.keys if term in key] for term in terms}

    def fetch_food_facts(self, canonical_keys):
        return {key: FoodFacts(canonical_key=key, canonical_name=key, fdc_id=None, description=None,
                               nutrients=NutrientProfile(calories_kcal=1.0)) for key in canonical_keys}


def calculate(repository, *names):
    request = CostNutritionRequest(servings=1, ingredients=[
        {"name": name, "quantity": 10, "unit": "g"} for name in names])
    return CostNutritionService(repository).calculate(request)


def test_plural_and_aliased_names_find_pipeline_keys():
    repository = FakeRepository(["bay leave", "tomatoe", "cherry tomatoe", "rolled oats"])
    response = calculate(repository, "Bay Leaves", "Tomatoes", "Oatmeal")
    assert [item.canonical_name for item in response.itemized] == ["bay leave", "tomatoe", "rolled oats"]
    assert repository.searched == ["bay leaf", "bay leave", "tomato", "tomatoe", "oatmeal", "rolled oat", "rolled oats"]
