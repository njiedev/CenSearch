import Logo from './Logo'
import PhotoGrid from './PhotoGrid'
import SignUp from './SignUp'
import Viewfinder from './Viewfinder'

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
            <a className="hero-cta" href="#signup">
              Start here
            </a>
          </div>
          <p className="scroll-hint">Scroll</p>
        </section>
        {/* One blur layer behind both sections, so there's no seam between them. */}
        <div className="blurred">
          <section className="desk" id="about">
            <Viewfinder />
          </section>
          <section className="signup" id="signup" aria-labelledby="signup-title">
            <SignUp />
          </section>
        </div>
      </main>
    </>
  )
}
