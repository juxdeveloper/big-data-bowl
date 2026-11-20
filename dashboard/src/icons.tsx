/** Iconos en la retícula de 24 px de Material, dibujados a mano: cero dependencias. */
type P = { size?: number; className?: string }

const S = ({ size = 24, className, d }: P & { d: string }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    className={className}
    fill="currentColor"
    aria-hidden="true"
    focusable="false"
  >
    <path d={d} />
  </svg>
)

export const IconSun = (p: P) => (
  <S
    {...p}
    d="M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10zm0-5 2 3h-4l2-3zm0 20-2-3h4l-2 3zM2 12l3-2v4l-3-2zm20 0-3 2v-4l3 2zM5.6 5.6l3.3 1.2-2.1 2.1L5.6 5.6zm12.8 12.8-3.3-1.2 2.1-2.1 1.2 3.3zM18.4 5.6l-1.2 3.3-2.1-2.1 3.3-1.2zM5.6 18.4l1.2-3.3 2.1 2.1-3.3 1.2z"
  />
)

export const IconMoon = (p: P) => (
  <S {...p} d="M12.3 2a9 9 0 1 0 9.7 11.5 7.5 7.5 0 0 1-9.7-9.7c0-.6 0-1.2.1-1.8z" />
)

export const IconShield = (p: P) => <S {...p} d="M12 2 4 5v6c0 5 3.4 9.4 8 11 4.6-1.6 8-6 8-11V5l-8-3z" />

export const IconTarget = (p: P) => (
  <S
    {...p}
    d="M12 4a8 8 0 1 0 0 16 8 8 0 0 0 0-16zm0 2.5a5.5 5.5 0 1 1 0 11 5.5 5.5 0 0 1 0-11zm0 3a2.5 2.5 0 1 0 0 5 2.5 2.5 0 0 0 0-5z"
  />
)

export const IconGroups = (p: P) => (
  <S
    {...p}
    d="M12 6a2.6 2.6 0 1 0 0 5.2A2.6 2.6 0 0 0 12 6zm-6 1a2.2 2.2 0 1 0 0 4.4A2.2 2.2 0 0 0 6 7zm12 0a2.2 2.2 0 1 0 0 4.4A2.2 2.2 0 0 0 18 7zM6 12.8c-2.2 0-4 1.2-4 2.7V18h8v-2.5c0-1.5-1.8-2.7-4-2.7zm12 0c-2.2 0-4 1.2-4 2.7V18h8v-2.5c0-1.5-1.8-2.7-4-2.7zm-6 .6c-2.4 0-4.4 1.3-4.4 2.9V19h8.8v-2.7c0-1.6-2-2.9-4.4-2.9z"
  />
)

export const IconChart = (p: P) => <S {...p} d="M4 19h16v2H4v-2zM6 10h3v7H6v-7zm4.5-5h3v12h-3V5zM15 13h3v4h-3v-4z" />

export const IconSend = (p: P) => <S {...p} d="M3 20.5 21 12 3 3.5 3 10l12 2-12 2v6.5z" />

export const IconClose = (p: P) => (
  <S {...p} d="M18.3 7.1 16.9 5.7 12 10.6 7.1 5.7 5.7 7.1l4.9 4.9-4.9 4.9 1.4 1.4 4.9-4.9 4.9 4.9 1.4-1.4-4.9-4.9 4.9-4.9z" />
)

export const IconBack = (p: P) => <S {...p} d="M20 11H7.8l5.6-5.6L12 4l-8 8 8 8 1.4-1.4L7.8 13H20v-2z" />

export const IconSpeed = (p: P) => (
  <S
    {...p}
    d="M12 4a9 9 0 0 0-9 9c0 2 .6 3.7 1.7 5.2l1.6-1.2A7 7 0 0 1 12 6a7 7 0 0 1 5.7 11l1.6 1.2A9 9 0 0 0 12 4zm1.4 5.6-4.2 4.2a2 2 0 1 0 2.8 2.8l4.2-4.2-2.8-2.8z"
  />
)

export const IconBolt = (p: P) => <S {...p} d="M13 2 4 14h6l-1 8 9-12h-6l1-8z" />

export const IconFlag = (p: P) => <S {...p} d="M6 3h2v18H6V3zm3 1h11l-2.2 4L20 12H9V4z" />

export const IconSchool = (p: P) => <S {...p} d="M12 3 1 9l11 6 9-4.9V17h2V9L12 3zM5 14.2V18c0 1.7 3.1 3 7 3s7-1.3 7-3v-3.8l-7 3.8-7-3.8z" />

export const IconScale = (p: P) => <S {...p} d="M11 3h2v2.3l6 2V7h2v2l-2 5h-2l-2-5 .9-.3L13 7.6V19h4v2H7v-2h4V7.6l-2.9 1L9 9l-2 5H5l-2-5V7h2v.3l6-2V3z" />

export const IconHeight = (p: P) => <S {...p} d="M12 2 8 6h3v12H8l4 4 4-4h-3V6h3l-4-4zM3 3h2v18H3V3zm16 0h2v18h-2V3z" />

export const IconCake = (p: P) => (
  <S {...p} d="M12 2c.8 1 .8 2-.1 2.9.9.9 1 2 .1 2.9-1-1-1-2-.1-2.9C11 4 11 3 12 2zM7 9h10a3 3 0 0 1 3 3v1.5c-1 .8-2 .8-3 0-1 .8-2 .8-3 0-1 .8-2 .8-3 0-1 .8-2 .8-3 0-1 .8-2 .8-3 0V12a3 3 0 0 1 3-3zM4 16.5c1 .8 2 .8 3 0 1 .8 2 .8 3 0 1 .8 2 .8 3 0 1 .8 2 .8 3 0 1 .8 2 .8 3 0V20H4v-3.5z" />
)

export const IconHelmetTag = (p: P) => (
  <S {...p} d="M4 14a8 8 0 0 1 16 0v2H4v-2zm0 4h11a3 3 0 0 1 0 5H8a4 4 0 0 1-4-5z" />
)

export const IconSearch = (p: P) => (
  <S {...p} d="M15.5 14h-.8l-.3-.3a6.5 6.5 0 1 0-.7.7l.3.3v.8l5 5 1.5-1.5-5-5zm-5.5 0a4 4 0 1 1 0-8 4 4 0 0 1 0 8z" />
)
