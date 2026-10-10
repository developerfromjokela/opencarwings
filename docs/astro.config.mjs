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
      defaultLocale: 'root',
      locales: {
        root: {
          label: 'English',
          lang: 'en',
        },
        hu: {
          label: 'Magyar',
          lang: 'hu',
        },
      },
      sidebar: [
          {
            label: 'Vehicle Setup Guides',
            translations: {
              hu: 'Járműbeállítási útmutatók',
            },
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
            translations: {
              hu: 'Adatcsatornák',
            },
            items: [
                { autogenerate: { directory: 'datachannels' } },
            ],
		  },
          {
			label: 'OpenCARWINGS Server',
			translations: {
			  hu: 'OpenCARWINGS szerver',
			},
			items: [
			  { autogenerate: { directory: 'selfhosting' } },
			],
		  }
		]
    }),
  ],
});
