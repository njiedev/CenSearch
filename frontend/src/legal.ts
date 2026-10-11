export const CONTACT_EMAIL = 'njiedoescs@gmail.com'

export type LegalSection = {
  id: string
  title: string
  paragraphs: string[]
}

export type LegalDocument = {
  title: string
  introduction: string
  sections: LegalSection[]
}

export const privacy: LegalDocument = {
  title: 'Privacy Policy',
  introduction: 'Your face is personal. This policy explains what CenSearch collects, how the current demo uses it, and how to ask us to remove it.',
  sections: [
    {
      id: 'information',
      title: 'Information we collect',
      paragraphs: [
        'When you enroll, we collect the name you provide, your uploaded face photos, any original photos you choose to add, and your consent and ownership statements. We create numerical face representations, called embeddings, to compare your photos with images found during a search. These representations may be considered biometric information under applicable law.',
        'A search can also create records of matching images, public URLs, page text, screenshots, match results, removal drafts, approvals and request history. Our hosting infrastructure may record technical information such as IP addresses, request times and errors.',
        'If you contact us, we receive your email address and the information you choose to include in your message. Please do not email face photos, identification documents or intimate images.',
      ],
    },
    {
      id: 'use',
      title: 'How we use information',
      paragraphs: [
        'We use this information to enroll you, compare images, show potential matches, prepare removal requests, record your decisions and help resolve problems with the service. Your consent to process face photos is requested during enrollment.',
        'We do not sell your personal information, use your uploaded photos for advertising, or use them to train an AI model. You keep ownership of the content you upload.',
      ],
    },
    {
      id: 'processing',
      title: 'Where processing happens',
      paragraphs: [
        'Face detection and matching run on the CenSearch server. Your uploaded face photos and face embeddings are not sent to our language model. The model can receive page text and URLs to help assess a page, choose a route and find a recipient.',
        'Depending on the deployment, infrastructure providers, including Akamai for hosting, inference or object storage, may process information on our behalf. An inference provider receives the text supplied to the model; storage providers may hold uploaded photos and evidence. Server processing is different from keeping everything on your own device.',
        'When you authorize sending, removal emails are processed by Resend and the recipient’s email provider. They contain the notice text, identified page and image URLs, and the contact details you entered. Face photos and evidence bundles are not attached. Website forms require manual submission.',
      ],
    },
    {
      id: 'retention',
      title: 'Retention and deletion',
      paragraphs: [
        'Demo records do not currently expire automatically. Enrollment photos, embeddings and related records remain in the deployment until they are deleted by its operator. Do not use the demo as permanent storage for your originals.',
        'To request access, a correction, deletion, or withdrawal of your consent, email us using the contact details below. Include your enrollment identifier if you have it. We may ask for enough information to verify that the request relates to you, without asking you to send sensitive photos by email.',
        'Deleting data from CenSearch does not delete photos or pages held by other websites. Support correspondence and records that must be preserved for a legal obligation may be retained separately. Rights and exceptions depend on the law that applies to you.',
      ],
    },
    {
      id: 'cookies',
      title: 'Cookies and external links',
      paragraphs: [
        'The current CenSearch frontend does not include advertising cookies or third-party analytics. Following an article or another external link takes you to a separate website with its own privacy practices.',
        'The contact form prepares a message in your email application. It does not submit a message to a website form service. Your email provider and our email provider process the message when you choose to send it.',
      ],
    },
    {
      id: 'security',
      title: 'Security and children',
      paragraphs: [
        'This is an early demonstration, not a service intended for storing highly sensitive material. No online service can guarantee complete security. Do not upload government identification, intimate images or photos of people who have not consented.',
        'CenSearch is intended for people aged 18 and over. If you believe a child’s information has been provided to us, contact us so we can investigate and remove it where appropriate.',
      ],
    },
    {
      id: 'updates',
      title: 'Changes and contact',
      paragraphs: [
        'We will update this page when our data practices change and provide additional notice or seek consent when required. The date above identifies the latest revision.',
        `For privacy questions or requests, contact the CenSearch project team at ${CONTACT_EMAIL}.`,
      ],
    },
  ],
}

export const terms: LegalDocument = {
  title: 'Terms of Service',
  introduction: 'These terms cover the CenSearch website and demo. By using the service, you agree to these terms. If you do not agree, please do not use it.',
  sections: [
    {
      id: 'service',
      title: 'About the service',
      paragraphs: [
        'CenSearch helps you find possible appearances of your face or copies of photos you own, assess potential removal routes and prepare requests. It is an experimental project. Features may change, become unavailable or be removed.',
        'After you authorize a batch, the agent can send eligible removal emails automatically when a sending account is connected. You may choose to review notices before sending. Requests requiring website forms remain drafts. The service does not promise that every match will be found or that any content will be removed.',
      ],
    },
    {
      id: 'eligibility',
      title: 'Eligibility and permission',
      paragraphs: [
        'You must be at least 18 years old and able to agree to these terms. Use face search for yourself, and upload only photos you are allowed to provide. You must have the necessary copyright rights before making a copyright claim.',
        'Do not use CenSearch to identify strangers, stalk or harass someone, impersonate another person, evade access restrictions, or collect information about people without permission. Do not upload intimate images or government identification documents.',
      ],
    },
    {
      id: 'content',
      title: 'Your content',
      paragraphs: [
        'Your photos and other content remain yours. You give CenSearch permission to store, process and display them as needed to perform the functions you request. This permission does not transfer ownership of your content.',
        'You are responsible for the accuracy of the information and permissions you provide. Keep your own copies of any originals. Our Privacy Policy explains how information is handled and how to request deletion.',
      ],
    },
    {
      id: 'requests',
      title: 'Matches and removal requests',
      paragraphs: [
        'A match is a suggestion, not proof of identity, ownership or unlawful use. Automated assessments can be wrong. Another photo of the same person does not establish copyright ownership, and legitimate uses of an image may not qualify for removal.',
        'You are responsible for checking the evidence, recipient, grounds and statements in a request. Accepting a batch warning records your own attestation; the agent cannot attest on your behalf. Never submit a notice you know is false or misleading.',
        'CenSearch does not provide legal advice or act as your lawyer. Seek qualified advice if you are unsure whether you have a valid claim or how to respond to a dispute.',
      ],
    },
    {
      id: 'acceptable-use',
      title: 'Acceptable use',
      paragraphs: [
        'Do not disrupt the service, bypass its safeguards, access another person’s records, submit malicious files, or use it for an unlawful purpose. We may restrict or suspend access where necessary to address misuse, security concerns or legal requirements.',
        'You may stop using CenSearch at any time. Contact us to request deletion of your enrollment and related information.',
      ],
    },
    {
      id: 'third-parties',
      title: 'Other websites and services',
      paragraphs: [
        'CenSearch may link to or depend on services operated by others. We do not control their content, availability, decisions or privacy practices. Their own terms apply when you use them.',
        'Removing an image from one page does not guarantee removal from search results, backups, reposts or other websites.',
      ],
    },
    {
      id: 'limits',
      title: 'Availability and responsibility',
      paragraphs: [
        'To the extent allowed by law, the demo is offered as available, without a promise that it will be uninterrupted, error-free or suitable for every purpose. You are responsible for decisions you make using its results.',
        'To the extent allowed by law, CenSearch and its operators are not responsible for indirect or consequential losses arising from use of the demo. These terms do not exclude liability, warranties or consumer rights that cannot legally be excluded, including protections that apply in your location.',
      ],
    },
    {
      id: 'updates',
      title: 'Changes and contact',
      paragraphs: [
        'We may revise these terms as the project develops. The date above will change when we do. Material changes will be communicated when required, and you may stop using the service if you do not accept them.',
        `For questions about these terms, contact the CenSearch project team at ${CONTACT_EMAIL}.`,
      ],
    },
  ],
}
