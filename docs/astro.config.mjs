// @ts-check
import { defineConfig } from 'astro/config';
import starlight from '@astrojs/starlight';

// https://astro.build/config
export default defineConfig({
  base: '/static/docs',
  trailingSlash: 'always',
  integrations: [
    starlight({
      title: 'OpenCARWINGS Docs',
      sidebar: [
          {
            label: 'Vehicle Setup Guides',
            items: [
              {
                label: 'NISSAN',
                items: [
                  { autogenerate: { directory: 'guides' } },
                ],
              }
			],
		  },
          {
            label: 'Data Channels',
            items: [
                { autogenerate: { directory: 'datachannels' } },
            ],
		  },
          {
			label: 'OpenCARWINGS Server',
			items: [
			  { autogenerate: { directory: 'selfhosting' } },
			],
		  }
		]
    }),
  ],
});