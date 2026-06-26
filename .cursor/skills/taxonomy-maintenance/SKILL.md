---
name: taxonomy-maintenance
description: Design and maintain MindForge taxonomy files from intermediate markdown frontmatter. Use when creating, reviewing, or updating taxonomy_state/taxonomy_v*.json from original_title, generated_title, and summary fields.
disable-model-invocation: true
---

# MindForge Taxonomy Maintenance

## Purpose

Use this skill to collaboratively design or update MindForge taxonomy files. The taxonomy is maintained deliberately, not regenerated automatically.

The taxonomy labels, category IDs, descriptions, and subtopics must be in Simplified Chinese.

## Source Files

Read these inputs before proposing taxonomy changes:

1. `taxonomy_state/taxonomy_v*.json`: existing taxonomy versions.
2. `intermediate_markdowns/*.md`: every intermediate markdown file.
3. From each markdown file, use only these frontmatter fields for taxonomy design:
   - `original_title`
   - `generated_title`
   - `summary`

Do not use full conversation bodies for taxonomy design unless the user explicitly asks. The taxonomy should reflect the note corpus at the title and summary level.

## Scalable Corpus Methodology

Do not put every full markdown file into one prompt. Use a compact map-reduce workflow:

1. Extract a frontmatter inventory:
   - For every `intermediate_markdowns/*.md` file, collect `path`, `original_title`, `generated_title`, and `summary`.
   - Do not regenerate titles or summaries. Use the existing frontmatter values.
   - Keep the inventory compact; exclude markdown body content.

2. Batch large corpora:
   - If the corpus is too large for one reasoning pass, split the inventory into batches of about 30-50 notes.
   - For each batch, summarize only recurring themes, candidate categories, repeated subtopics, and ambiguous notes.
   - Do not carry every note verbatim into the final synthesis.

3. Synthesize globally:
   - Merge batch-level themes into a single taxonomy proposal.
   - Prefer categories that explain multiple notes across batches.
   - Use `subtopics` for repeated narrow concepts that are important but not broad enough to become primary categories.

4. Audit coverage:
   - Check whether every note can reasonably fit one primary category.
   - If many notes fall into `其他` or `不明确`, revise the category design before proposing JSON.
   - Call out any notes whose frontmatter is too weak to classify confidently.

5. Present evidence lightly:
   - Use representative titles as examples.
   - Avoid dumping long inventories into the response unless the user asks.

## Working Style

Always separate taxonomy thinking from file writing:

1. Read the current taxonomy and all intermediate markdown frontmatter.
2. Summarize the corpus themes in plain language.
3. Propose the taxonomy structure first.
4. Ask for user approval before writing or modifying any `taxonomy_state/taxonomy_v*.json` file.
5. When writing a new version, create a new file such as `taxonomy_state/taxonomy_v2.json`; do not overwrite an existing taxonomy unless the user explicitly asks.

## Recommended Structure

Prefer a mostly flat primary taxonomy with optional `subtopics`. This fits the current classifier and enrichment code, which selects `category_id` values from `categories`.

Use this JSON shape:

```json
{
  "version": "2.0",
  "generated_at": "ISO-8601 timestamp",
  "target_label_language": "zh-Hans",
  "design_notes": ["short Chinese notes about design decisions"],
  "categories": [
    {
      "category_id": "自我成长",
      "label": "自我成长",
      "description": "这个类别覆盖什么内容。",
      "subtopics": ["人生意义", "自我认知", "身份转型"],
      "include_examples": ["来自笔记标题的例子"],
      "exclude_examples": ["容易混淆但不属于此类的例子"]
    }
  ],
  "change_summary": {
    "kept": ["category_id"],
    "added": ["category_id"],
    "renamed": [{"from": "old_id", "to": "new_id"}],
    "deprecated": ["category_id"]
  }
}
```

## Design Principles

- Use Simplified Chinese for every category label, category ID, description, and subtopic.
- Use concise big-topic names for primary `category_id` and `label`, like `自我成长`, `情绪疗愈`, `亲密陪伴`, `家庭与代际`.
- Avoid explanatory compound labels like `自我成长与人生意义`, `情绪疗愈与心理调节`, or repeated `X与Y` naming unless the user explicitly asks.
- Prefer human meaning over technical neatness. The taxonomy should help the user find and understand notes later.
- Keep primary categories broad enough to avoid fragmentation, but not so broad that everything becomes "生活" or "成长".
- Use `subtopics` for nuance such as `灾难化心理`, `分离焦虑`, `婚姻`, `生育`, `原生家庭`, and `人生意义`.
- Preserve stable categories when they still fit the corpus.
- Rename categories when the new name better matches the user's language and future retrieval habits.
- Avoid mixing emotional themes and practical domains when a note clearly belongs to one stronger frame.
- Add `其他` and `不明确` only as fallbacks, not as normal design shortcuts.

## Suggested Primary Categories

Use this as the starting architecture, then adapt to the actual corpus:

- `自我成长`: 自我认知、身份转型、规则内化、自主决策、人生意义、价值观重建。
- `情绪疗愈`: 焦虑、灾难化心理、分离焦虑、内在安全感、情绪调节、认知重构。
- `亲密陪伴`: 恋爱关系、伴侣沟通、依恋与独立、承诺、婚姻仪式、跨文化相处。
- `家庭与代际`: 原生家庭、父母关系、代际边界、家庭责任、婚姻观、生育观。
- `职业发展`: 职场困境、咨询项目、团队文化、晋升、跳槽、领导力、工作边界。
- `生活方式`: 日常节奏、低压生活、居家办公、社交能量、个人习惯、体验探索。
- `旅行体验`: 旅行规划、行前准备、在地文化、旅行消费、旅行叙事。
- `健康身体`: 睡眠、运动、饮食、护肤、外在形象、身体数据与健康设备。
- `财富居住`: 理财、财务自由、保险、住房、装修、家居空间、消费决策。
- `创意表达`: 文案、脚本、散文、影评、小红书内容、礼物祝福、品牌表达。
- `技术知识`: AI工具、智能体、知识管理、技术方案、产品研究、自动化流程。
- `哲思象征`: 世界观、人类与AI、命理、象征叙事、存在体验、精神性探索。
- `其他`: 确实无法归入以上类别但内容清楚的笔记。
- `不明确`: 标题和摘要不足以判断主题的笔记。

## Proposal Format

Before editing files, present the taxonomy proposal like this:

```markdown
## Corpus Themes
[Short summary of the themes found across intermediate markdowns.]

## Proposed Taxonomy
- 类别名: description
  Subtopics: ...
  Why: ...

## Changes From Current Taxonomy
- Keep: ...
- Rename: ...
- Add: ...
- Deprecate: ...

## Questions For Approval
[Only ask questions that block a good taxonomy decision.]
```

## Validation Checklist

Before writing a taxonomy JSON file:

- All category IDs and labels are Simplified Chinese.
- Every category has `category_id`, `label`, `description`, `subtopics`, `include_examples`, and `exclude_examples`.
- Category IDs are unique.
- The taxonomy includes `其他` and `不明确`.
- Examples come from real note titles when possible.
- The file is valid JSON.
- Existing taxonomy files are not overwritten without explicit user approval.
