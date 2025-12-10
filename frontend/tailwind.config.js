/** @type {import('tailwindcss').Config} */
export default {
    content: [
        "./index.html",
        "./src/**/*.{js,ts,jsx,tsx}",
    ],
    theme: {
        extend: {
            colors: {
                coral: {
                    500: '#E07A5F',
                    600: '#C96A52',
                },
                charcoal: {
                    500: '#3D405B',
                },
                cream: '#FFF8F0',
                sage: '#81B29A',
            }
        },
    },
    plugins: [],
}
