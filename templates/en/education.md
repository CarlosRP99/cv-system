## Education

{{#each education}}
### {{degree.en}} — {{institution.en}}
{{formatDate startDate}} – {{formatDate endDate}}

{{#if description.en}}{{description.en}}{{/if}}

{{/each}}
