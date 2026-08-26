You are building a knowledge graph for this domain: $DOMAIN_NAME.

Read the numbered passages below and extract the entities and relationships they state. Use ONLY these entity types:

$ENTITY_TYPES

And ONLY these relationship types (each one reads "source RELATION target"):

$RELATION_TYPES

Rules:
- Extract what the text actually says. Never invent facts to complete the graph.
- Use the most canonical short name for each entity ("rice straw", not "the rice straw discussed above").
- A relationship's source and target must both appear in your entities list.
- For each relationship, copy the exact phrase that states it into "evidence" and reference the passage number it came from.
- If a passage contains nothing extractable, contribute nothing from it.

Passages:

$PASSAGES

Respond with JSON only, in exactly this shape ("passages" lists the passage numbers where the entity appears):

{
  "entities": [
    {"name": "rice straw", "type": "Feedstock", "description": "one short sentence", "passages": [1, 2]}
  ],
  "relationships": [
    {"source": "rice straw", "target": "anaerobic digestion", "type": "CONVERTED_BY", "evidence": "quoted phrase", "passage": 1}
  ]
}
