import Logo from './Logo'
import Monitor from './Monitor'
import NavBar from './NavBar'
import PhotoGrid from './PhotoGrid'

export default function App() {
  return (
    <>
      <PhotoGrid />
      <NavBar />
      <main>
        <section className="hero" id="top">
          <Logo />
          <p className="scroll-hint">Scroll</p>
        </section>
        <section className="desk" id="how-it-works" aria-labelledby="desk-title">
          <h2 className="desk-title" id="desk-title">
            The agent does the legwork.
            <br />
            You sign off.
          </h2>
          <Monitor />
        </section>
      </main>
    </>
  )
}
