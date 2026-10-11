const questions = [
  {
    question: 'Where do my photos go?',
    answer: 'They stay on our server. Face matching runs there, and your photos are never sent to the AI model or to a cloud face service. The model only sees page text and links.',
  },
  {
    question: 'Do you send requests to real websites?',
    answer: 'Not in this demo. Requests are sent only to mock sites we run ourselves. For a real site you get the drafted request and the right recipient, and you send it.',
  },
  {
    question: 'Who is legally responsible for a request?',
    answer: 'You are. The agent picks the route and fills in a fixed template, and you accept a warning before each batch is sent.',
  },
  {
    question: 'What happens if a site says no?',
    answer: 'If a site ignores the request, we move up to its host and then to search engines. If it gives a real reason, such as licensed editorial use, we stop and show you the reply instead of escalating.',
  },
  {
    question: "What can't it find?",
    answer: 'Faces in small thumbnails and heavily covered faces are often missed. Copies of a photo are still caught when you gave us the original.',
  },
  {
    question: 'Can it see what is in an image?',
    answer: 'No. The agent reads the page around an image, not the image itself, so it cannot judge on its own whether a picture is intimate. Those cases are held for you to review.',
  },
]

export default function Faq() {
  return (
    <section className="faq landing-section" id="faq" aria-labelledby="faq-title">
      <h2 id="faq-title">Questions people ask</h2>
      <p className="section-sub">Straight answers, including the limits.</p>
      <div className="faq-list">
        {questions.map(({ question, answer }, index) => (
          <details className="faq-item" name="landing-faq" key={question} open={index === 0}>
            <summary>
              <span className="faq-question">{question}</span>
              <span className="faq-toggle" aria-hidden="true"><span /></span>
            </summary>
            <p>{answer}</p>
          </details>
        ))}
      </div>
    </section>
  )
}
