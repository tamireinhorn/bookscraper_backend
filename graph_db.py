from neomodel import config, db, ConstraintValidationFailed
import os
from graph_models import Author, City, Country, Region
from typing import List, Dict

NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
config.DATABASE_URL = f"bolt://neo4j:{NEO4J_PASSWORD}@localhost:7687"


# TODO: This is not efficient, as every author created is a roundtrip to the DB...
@db.transaction
def insert_author(author: Dict):
    if "name" not in author or not author["name"]:
        raise ValueError(f"Missing name for this author dict: {author}")
    # TODO: Here, we don't get the author's relationship with city.
    author_node = Author.get_or_create(
        {"goodreads_id": author["goodreads_id"], "name": author["name"]},
        defaults=author,
    )
    return author_node


def city_region_exists(city_name: str, region_name: str) -> bool:
    query = """
    MATCH (c:City)-[:WITHIN]->(r:Region {name: $region_name})
    WHERE c.name = $city_name
    RETURN c
    """
    results, meta = db.cypher_query(
        query, {"city_name": city_name, "region_name": region_name}
    )
    return len(results) > 0

def city_country_exists(city_name: str, country_name: str) -> bool:
    query = """
    MATCH (c:City)-[:WITHIN]->(r:Country {name: $country_name})
    WHERE c.name = $city_name
    RETURN c
    """
    results, meta = db.cypher_query(
        query, {"city_name": city_name, "country_name": country_name}
    )
    return len(results) > 0


def region_country_exists(country_name: str, region_name: str) -> bool:
    query = """
    MATCH (r:Region)-[:WITHIN]->(c:Country {name: $country_name})
    WHERE r.name = $region_name
    RETURN r
    """
    results, meta = db.cypher_query(
        query, {"country_name": country_name, "region_name": region_name}
    )
    return len(results) > 0


@db.transaction
def geo_nodes(geo_dict: Dict[str, str]):
    try:
        # The first node we should create is country, which already has a uniqueness check. All good on this front then.
        c = Country.get_or_create({"name": geo_dict["country"]})
        country_node = c[0]
        # Then, we create the city node.
        city_node = create_or_get_city(geo_dict)
        city_node.save()
        if "region" in geo_dict:
            region_node = create_or_get_region(geo_dict)
            region_node.save()
            if not region_node.country.is_connected(country_node):
                region_node.country.connect(country_node)
            
            # If there is region, then city connects to region:
            if not city_node.region.is_connected(region_node):
                city_node.region.connect(region_node)
        else:
            # If there is no region, city connects to country:
            if not city_node.country.is_connected(country_node):
                city_node.country.connect(country_node)
    except Exception as e:
        print(e)


def create_or_get_region(geo_dict: Dict[str, str]) -> Region:
    """Creates a Region node if and only if it satisfies the validation criteria.

    Args:
        geo_dict (Dict[str, str]): Geographical information.

    Returns:
        Region: The desired region node.
    """
    # Validate constraints
    if not region_country_exists(geo_dict["country"], geo_dict["region"]):
        # If this doesn't exist, we shoud create it. But we will connect and then save!!
        region_node = Region(name = geo_dict["region"])
    else:
        print(f"The region {geo_dict["region"]} already exists within {geo_dict["country"]} so we didn't create it.")
        region_node =  Region.nodes.get(name = geo_dict["region"])
    return region_node



def create_or_get_city(geo_dict: Dict[str, str]) -> City:
    """Creates a City node if and only if it satisfies the validation criteria.

    Args:
        geo_dict (Dict[str, str]): Geographical information.

    Returns:
        City: The desired City node.
    """
    # Validate constraints.
    if not city_country_exists(geo_dict["city"], geo_dict["country"]) and not city_region_exists(geo_dict["city"], geo_dict["region"]):
        # If this doesn't exist, we shoud create it. But we will connect and then save!!
        city_node = City(name = geo_dict["city"])
    else:
        print(f"This combination for city already exists, so we didn't create it..")
        city_node =  City.nodes.get(name = geo_dict["city"])
    return city_node

def create_constraints():
    queries = [
        "CREATE CONSTRAINT country_name FOR (country:Country) REQUIRE country.name IS UNIQUE",
    ]
    for query in queries:
        try:
            db.cypher_query(query)
        except Exception as e:
            print(f"Error creating constraint: {e}")


if __name__ == "__main__":
    # create_constraints()
    geo_dict = {
        "country": "Brazil",
        "city": "Rio de Janeiro",
        "region": "Rio de Janeiro",
    }
    geo_nodes(geo_dict)
