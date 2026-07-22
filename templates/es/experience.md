## Experiencia Profesional

{{#each experiences}}
### {{role.es}} — {{company}}
{{formatDate startDate}} – {{#if endDate}}{{formatDate endDate}}{{else}}Presente{{/if}} | {{location}}

{{description.es}}

{{#each highlights.es}}
- {{this}}
{{/each}}

{{/each}}
