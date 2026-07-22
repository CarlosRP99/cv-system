## Proyectos Destacados

{{#each projects}}
### {{name}}
{{formatDate startDate}} – {{formatDate endDate}} | {{role.es}}

{{description.es}}

{{#each highlights.es}}
- {{this}}
{{/each}}

{{/each}}
