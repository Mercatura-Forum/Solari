/** Vite serves `?url` imports as the asset's URL in the built bundle. */
declare module '*?url' {
  const src: string
  export default src
}
