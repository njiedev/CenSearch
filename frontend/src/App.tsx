import Logo from './Logo'
import PhotoGrid from './PhotoGrid'

export default function App() {
  return (
    <>
      <PhotoGrid />
      <main>
        <section className="hero" id="top">
          <div className="hero-copy">
            <Logo />
            <h2 className="hero-headline">
              Your <span className="pixel-word">face</span> is out there.
              <br />
              We take it <span className="pixel-word">down</span>.
            </h2>
            <p className="hero-sub">
              We search the web for your face and send deletion requests wherever they're needed.
            </p>
            <a className="hero-cta" href="/signup.html">
              Start here
            </a>
          </div>
        </section>
      </main>
    </>
  )
}
