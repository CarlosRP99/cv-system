## Professional Experience

{{#each experiences}}
### {{role.en}} — {{company}}
{{formatDate startDate}} – {{#if endDate}}{{formatDate endDate}}{{else}}Present{{/if}} | {{location}}

{{description.en}}

{{#each highlights.en}}
- {{this}}
{{/each}}

{{/each}}
