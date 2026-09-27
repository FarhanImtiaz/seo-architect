export const metadata = {
  title: {
    template: "%s | Example",
    default: "Example",
  },
};

export default function RootLayout({ children }) {
  return <html><body>{children}</body></html>;
}
