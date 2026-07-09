"""
Ontology Generation Service
Interface 1: Analyze text content to generate entity and relationship type definitions suitable for marketing campaign audience simulation
"""

import json
import logging
from typing import Dict, Any, List, Optional
from ..utils.llm_client import LLMClient

logger = logging.getLogger(__name__)


# System prompt for ontology generation
ONTOLOGY_SYSTEM_PROMPT = """You are a professional knowledge graph ontology design expert. Your task is to analyze given text content and simulation requirements to design entity types and relationship types suitable for **marketing campaign audience simulation**.

**Important: You must output valid JSON format data. Do not output anything else.**

## Core Task Background

We are building a **marketing campaign audience simulation system**. In this system:
- Each entity is a consumer, brand, or market actor that can react to campaigns, share opinions, and influence purchasing decisions
- Entities interact through purchasing behavior, brand advocacy, word-of-mouth, reviews, and competitive dynamics
- We need to simulate how different consumer segments and market participants react to marketing campaigns

Therefore, **entities must be real-world actors that can participate in market dynamics and express opinions**:

**Can be**:
- Consumer segments (young consumers, price-sensitive shoppers, brand loyalists, early adopters, premium buyers, parent consumers)
- Market influencers (social media influencers, industry analysts, product reviewers)
- Brands and companies (including their official accounts)
- Retail and distribution channels
- Marketing agencies
- Industry press and media outlets
- Organizations and institutions (trade associations, consumer advocacy groups)

**Cannot be**:
- Abstract concepts (e.g., "brand equity", "market trend", "consumer sentiment")
- Topics/themes (e.g., "sustainability", "digital transformation")
- Opinions/attitudes (e.g., "supporters", "detractors")

## Output Format

Please output JSON format with the following structure:

```json
{
    "entity_types": [
        {
            "name": "Entity type name (English, PascalCase)",
            "description": "Brief description (English, max 100 characters)",
            "attributes": [
                {
                    "name": "attribute_name (English, snake_case)",
                    "type": "text",
                    "description": "Attribute description"
                }
            ],
            "examples": ["Example entity 1", "Example entity 2"]
        }
    ],
    "edge_types": [
        {
            "name": "Relationship type name (English, UPPER_SNAKE_CASE)",
            "description": "Brief description (English, max 100 characters)",
            "source_targets": [
                {"source": "Source entity type", "target": "Target entity type"}
            ],
            "attributes": []
        }
    ],
    "analysis_summary": "Brief analysis summary of the text content"
}
```

## Design Guidelines (Extremely Important!)

### 1. Entity Type Design - Must Be Strictly Followed

**Quantity requirement: Exactly 10 entity types**

**Hierarchy requirements (must include both specific types and fallback types)**:

Your 10 entity types must include the following layers:

A. **Fallback types (must be included, placed as the last 2 in the list)**:
   - `Person`: Fallback type for any individual. When a person does not belong to other more specific person types, classify them here.
   - `Organization`: Fallback type for any organization. When an organization does not belong to other more specific organization types, classify them here.

B. **Specific types (8, designed based on text content)**:
   - Design more specific types based on the main actors appearing in the text
   - Example: If the text involves cosmetics marketing, you could have `YoungConsumer`, `BeautyInfluencer`, `CosmeticsBrand`
   - Example: If the text involves tech products, you could have `EarlyAdopter`, `TechReviewer`, `RetailChannel`
   - Example: If the text involves food/beverage, you could have `HealthConsciousConsumer`, `FoodBlogger`, `GroceryChain`

**Why fallback types are needed**:
- Text will contain various actors like "random shopper", "a customer", "some user"
- If there is no specific type match, they should be classified as `Person`
- Similarly, small businesses, temporary groups, etc. should be classified as `Organization`

**Design principles for specific types**:
- Identify high-frequency or key actor types from the text
- Each specific type should have clear boundaries, avoiding overlap
- Description must clearly explain the difference between this type and the fallback type

### 2. Relationship Type Design

- Quantity: 6-10
- Relationships should reflect real connections in marketing and consumer dynamics
- Ensure relationship source_targets cover your defined entity types

### 3. Attribute Design

- 1-3 key attributes per entity type
- **Note**: Attribute names cannot use `name`, `uuid`, `group_id`, `created_at`, `summary` (these are system reserved words)
- Recommended: `full_name`, `title`, `role`, `position`, `location`, `description`, `brand_affinity`, `price_sensitivity`, etc.

## Entity Type Reference

**Consumer types (specific)**:
- YoungConsumer: Young consumers (18-30), trend-sensitive, social media active
- PriceSensitiveShopper: Budget-conscious consumers focused on deals and value
- BrandLoyalist: Consumers with strong existing brand preferences
- EarlyAdopter: Tech/trend-forward consumers who try new products first
- PremiumBuyer: High-spending consumers seeking quality and exclusivity
- ParentConsumer: Family-oriented consumers with household purchasing focus

**Individual types (specific)**:
- Influencer: Social media influencers and content creators
- IndustryAnalyst: Market researchers, analysts, and domain experts

**Individual (fallback)**:
- Person: Any individual (used when no other specific type matches)

**Organization types (specific)**:
- CompetitorBrand: Competing brands in the market
- RetailChannel: Retail stores, e-commerce platforms, distributors
- MarketingAgency: Advertising and marketing service providers
- IndustryPress: Trade publications, industry media, review outlets
- Company: General business entities

**Organization (fallback)**:
- Organization: Any organization (used when no other specific type matches)

## Relationship Type Reference

- PURCHASES_FROM: Buys products/services from
- COMPETES_WITH: Competes in the same market
- INFLUENCES: Influences purchasing decisions or opinions
- RECOMMENDS: Recommends products or brands
- REVIEWS: Reviews or evaluates products
- DISTRUSTS: Has negative sentiment or distrust toward
- FOLLOWS_BRAND: Follows or is loyal to a brand
- DISTRIBUTES: Distributes or sells products for
- PARTNERS_WITH: Has a business partnership with
- TARGETS: Targets as a customer segment
"""


class OntologyGenerator:
    """
    Ontology Generator
    Analyzes text content to generate entity and relationship type definitions
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()

    def generate(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate ontology definitions

        Args:
            document_texts: List of document texts
            simulation_requirement: Simulation requirement description
            additional_context: Additional context

        Returns:
            Ontology definition (entity_types, edge_types, etc.)
        """
        # Build user message
        user_message = self._build_user_message(
            document_texts,
            simulation_requirement,
            additional_context
        )

        messages = [
            {"role": "system", "content": ONTOLOGY_SYSTEM_PROMPT},
            {"role": "user", "content": user_message}
        ]

        # Call LLM
        result = self.llm_client.chat_json(
            messages=messages,
            temperature=0.3,
            max_tokens=4096
        )

        # Validate and post-process
        result = self._validate_and_process(result)

        return result

    # Maximum text length sent to LLM (50k characters)
    MAX_TEXT_LENGTH_FOR_LLM = 50000

    def _build_user_message(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str]
    ) -> str:
        """Build user message"""

        # Combine texts
        combined_text = "\n\n---\n\n".join(document_texts)
        original_length = len(combined_text)

        # Truncate if text exceeds 50k characters (only affects LLM input, not graph building)
        if len(combined_text) > self.MAX_TEXT_LENGTH_FOR_LLM:
            combined_text = combined_text[:self.MAX_TEXT_LENGTH_FOR_LLM]
            combined_text += f"\n\n...(Original text: {original_length} chars, truncated to first {self.MAX_TEXT_LENGTH_FOR_LLM} chars for ontology analysis)..."

        message = f"""## Campaign Brief / Simulation Requirement

{simulation_requirement}

## Document Content

{combined_text}
"""

        if additional_context:
            message += f"""
## Additional Notes

{additional_context}
"""

        message += """
Based on the above content, design entity types and relationship types suitable for marketing campaign audience simulation.

**Rules that must be followed**:
1. Must output exactly 10 entity types
2. The last 2 must be fallback types: Person (individual fallback) and Organization (organization fallback)
3. The first 8 are specific types designed based on the text content
4. All entity types must be real-world actors that can participate in market dynamics, not abstract concepts
5. Attribute names cannot use reserved words like name, uuid, group_id — use full_name, org_name, etc. instead
"""

        return message

    def _validate_and_process(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and post-process results"""

        # Ensure required fields exist
        if "entity_types" not in result:
            result["entity_types"] = []
        if "edge_types" not in result:
            result["edge_types"] = []
        if "analysis_summary" not in result:
            result["analysis_summary"] = ""

        # Validate entity types
        for entity in result["entity_types"]:
            if "attributes" not in entity:
                entity["attributes"] = []
            if "examples" not in entity:
                entity["examples"] = []
            # Ensure description does not exceed 100 characters
            if len(entity.get("description", "")) > 100:
                entity["description"] = entity["description"][:97] + "..."

        # Validate relationship types
        # Zep API limit: each edge can have at most 10 source_targets pairs.
        MAX_SOURCE_TARGETS_PER_EDGE = 10
        for edge in result["edge_types"]:
            if "source_targets" not in edge:
                edge["source_targets"] = []
            if "attributes" not in edge:
                edge["attributes"] = []
            if len(edge.get("description", "")) > 100:
                edge["description"] = edge["description"][:97] + "..."
            sts = edge["source_targets"]
            if len(sts) > MAX_SOURCE_TARGETS_PER_EDGE:
                logger.warning(
                    "Edge '%s' has %d source_targets, trimming to Zep's max of %d",
                    edge.get("name", "?"), len(sts), MAX_SOURCE_TARGETS_PER_EDGE,
                )
                edge["source_targets"] = sts[:MAX_SOURCE_TARGETS_PER_EDGE]

        # Zep API limit: max 10 custom entity types, max 10 custom edge types
        MAX_ENTITY_TYPES = 10
        MAX_EDGE_TYPES = 10

        # Fallback type definitions
        person_fallback = {
            "name": "Person",
            "description": "Any individual person not fitting other specific person types.",
            "attributes": [
                {"name": "full_name", "type": "text", "description": "Full name of the person"},
                {"name": "role", "type": "text", "description": "Role or occupation"}
            ],
            "examples": ["ordinary consumer", "anonymous reviewer"]
        }

        organization_fallback = {
            "name": "Organization",
            "description": "Any organization not fitting other specific organization types.",
            "attributes": [
                {"name": "org_name", "type": "text", "description": "Name of the organization"},
                {"name": "org_type", "type": "text", "description": "Type of organization"}
            ],
            "examples": ["small business", "trade association"]
        }

        # Check if fallback types already exist
        entity_names = {e["name"] for e in result["entity_types"]}
        has_person = "Person" in entity_names
        has_organization = "Organization" in entity_names

        # Fallback types to add
        fallbacks_to_add = []
        if not has_person:
            fallbacks_to_add.append(person_fallback)
        if not has_organization:
            fallbacks_to_add.append(organization_fallback)

        if fallbacks_to_add:
            current_count = len(result["entity_types"])
            needed_slots = len(fallbacks_to_add)

            # If adding would exceed 10, remove some existing types
            if current_count + needed_slots > MAX_ENTITY_TYPES:
                to_remove = current_count + needed_slots - MAX_ENTITY_TYPES
                # Remove from the end (preserve more important specific types at front)
                result["entity_types"] = result["entity_types"][:-to_remove]

            # Add fallback types
            result["entity_types"].extend(fallbacks_to_add)

        # Final check: ensure within limits (defensive programming)
        if len(result["entity_types"]) > MAX_ENTITY_TYPES:
            result["entity_types"] = result["entity_types"][:MAX_ENTITY_TYPES]

        if len(result["edge_types"]) > MAX_EDGE_TYPES:
            result["edge_types"] = result["edge_types"][:MAX_EDGE_TYPES]

        return result
