// The sample person's photos in public/demo: three face photos and the eight
// pages the demo scan "finds". The backdrop grid and scan animation reuse them.
export const REFERENCE_PHOTOS = [1, 2, 3].map((index) => `/demo/reference/${index}.jpg`)
export const MATCH_PHOTOS = [1, 2, 3, 4, 5, 6, 7, 8].map((index) => `/demo/matches/${index}.jpg`)
export const DEMO_PHOTOS = [...REFERENCE_PHOTOS, ...MATCH_PHOTOS]
