// Real headlines about camera glasses and filming without consent. Each
// headline is copied from the page behind its URL; don't add one you haven't
// opened and read.
export type Article = {
  headline: string
  outlet: string
  date: string
  url: string
  size?: 'large' | 'small'
}

export const ARTICLES: Article[] = [
  {
    headline:
      'Woman covertly filmed by Meta AI smart glasses raises privacy and consent concerns: "I had no say"',
    outlet: 'CBS News',
    date: 'Aug 2026',
    url: 'https://www.cbsnews.com/news/meta-ai-smart-glasses-covert-filming-privacy',
    size: 'large',
  },
  {
    headline: 'Meta Faces Lawsuit Claiming Ray-Ban Smart Glasses Sent Private Footage to Overseas Reviewers',
    outlet: 'Road to VR',
    date: 'Mar 2026',
    url: 'https://roadtovr.com/meta-lawsuit-ray-ban-smart-glasses-privacy/',
    size: 'small',
  },
  {
    headline: "Women in Brussels 'filmed without their knowledge' by men wearing Meta smart glasses",
    outlet: 'The Brussels Times',
    date: 'Jun 2026',
    url: 'https://www.brusselstimes.com/news/2166072/women-unknowingly-filmed-in-brussels-with-meta-smart-glasses-raise-concerns/',
  },
  {
    headline: 'Harvard Students Use Meta Ray-Ban Glasses for AI-Powered Doxing',
    outlet: 'OECD.AI',
    date: 'Oct 2024',
    url: 'https://oecd.ai/en/incidents/2024-10-07-826b',
  },
  {
    headline: 'Seven million cameras on seven million faces: the smart glasses privacy crisis no one can stop',
    outlet: 'The Next Web',
    date: 'May 2026',
    url: 'https://thenextweb.com/news/meta-smart-glasses-privacy-crisis-apple-google-snap',
    size: 'large',
  },
  {
    headline: 'Meta, Luxottica Again Sued Over AI Smart Glasses Video Sharing',
    outlet: 'Bloomberg Law',
    date: 'Mar 2026',
    url: 'https://news.bloomberglaw.com/ip-law/meta-luxottica-again-sued-over-ai-smart-glasses-video-sharing',
    size: 'small',
  },
  {
    headline: 'What’s the Deal With Meta’s ‘Pervert Glasses’?',
    outlet: 'Decrypt',
    date: 'Aug 2026',
    url: 'https://decrypt.co/374808/whats-the-deal-with-meta-pervert-glasses',
  },
  {
    headline: 'Man Wearing Smart Glasses Secretly Records Woman, Demands Money to Delete Video From His Socials',
    outlet: 'Futurism',
    date: 'May 2026',
    url: 'https://futurism.com/future-society/man-smart-glasses-records-woman-demands-money',
    size: 'large',
  },
  {
    headline: 'Smart glasses users were secretly recording others. Meta says it found a fix',
    outlet: 'Straight Arrow News',
    date: 'Jul 2026',
    url: 'https://san.com/cc/smart-glasses-users-were-secretly-recording-others-meta-says-it-found-a-fix/',
  },
  {
    headline:
      'Privacy concerns grow as security researchers allege Meta’s smart glasses contain code that enables mass surveillance',
    outlet: 'Business & Human Rights Resource Centre',
    date: 'Jun 2026',
    url: 'https://www.business-humanrights.org/de/neuste-meldungen/privacy-concerns-grow-as-security-researchers-allege-metas-smart-glasses-contain-code-that-enables-mass-surveillance/',
    size: 'small',
  },
  {
    headline: 'Smart glasses are having a privacy reckoning, and Meta is caught in the middle',
    outlet: 'The Next Web',
    date: 'Jul 2026',
    url: 'https://thenextweb.com/news/smart-glasses-privacy-new-york-courthouse-ban-meta-recording-light',
  },
  {
    headline: 'New fear: Man films woman with smart glasses, seeks money to take video down',
    outlet: 'Bitdefender',
    date: 'May 2026',
    url: 'https://www.bitdefender.com/en-gb/blog/hotforsecurity/man-films-woman-smart-glasses-money',
    size: 'large',
  },
  {
    headline: 'Meta faces US class action lawsuit over Ray-Ban AI glasses privacy concerns',
    outlet: 'BusinessToday',
    date: 'Mar 2026',
    url: 'https://www.businesstoday.in/amp/technology/news/story/metas-ai-glasses-face-us-lawsuit-as-privacy-concerns-come-under-legal-scrutiny-519384-2026-03-06',
    size: 'small',
  },
  {
    headline: 'AI Glasses Meet the Law: From Meta Lawsuits to Courthouse Bans',
    outlet: 'FindLaw',
    date: 'Jul 2026',
    url: 'https://www.findlaw.com/legalblogs/technologist/ai-glasses-meet-the-law-from-meta-lawsuits-to-courthouse-bans/',
  },
]
