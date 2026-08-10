import { useTranslation } from 'react-i18next'

function LanguageSwitcher() {
  const { i18n } = useTranslation()

  const changeLanguage = (lng: string) => {
    i18n.changeLanguage(lng)
  }

  return (
    <div className="language-switcher">
      <button
        onClick={() => changeLanguage('en')}
        className={i18n.language === 'en' ? 'active' : ''}
      >
        English
      </button>
      <button
        onClick={() => changeLanguage('hi')}
        className={i18n.language === 'hi' ? 'active' : ''}
      >
        हिंदी
      </button>
    </div>
  )
}

export default LanguageSwitcher
