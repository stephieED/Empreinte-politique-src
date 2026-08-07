/* @ds-bundle: {"format":4,"namespace":"EmpreintePolitiqueDesignSystem_0817cb","components":[{"name":"Icon","sourcePath":"components/core/Icon.jsx"},{"name":"SectionKicker","sourcePath":"components/core/SectionKicker.jsx"},{"name":"Tag","sourcePath":"components/core/Tag.jsx"},{"name":"KpiCard","sourcePath":"components/data/KpiCard.jsx"},{"name":"ScopeBar","sourcePath":"components/data/ScopeBar.jsx"},{"name":"VoteCard","sourcePath":"components/data/VoteCard.jsx"},{"name":"OutcomeBar","sourcePath":"components/feedback/OutcomeBar.jsx"},{"name":"VoteBadge","sourcePath":"components/feedback/VoteBadge.jsx"},{"name":"CandidateRail","sourcePath":"components/navigation/CandidateRail.jsx"},{"name":"ModeSwitch","sourcePath":"components/navigation/ModeSwitch.jsx"},{"name":"PanelNav","sourcePath":"components/navigation/PanelNav.jsx"}],"sourceHashes":{"components/core/Icon.jsx":"1941dd6797c3","components/core/SectionKicker.jsx":"8e25815ff5cb","components/core/Tag.jsx":"d8c2ad2968a3","components/data/KpiCard.jsx":"10752cb8b94d","components/data/ScopeBar.jsx":"893e36dc0be5","components/data/VoteCard.jsx":"40488998d388","components/feedback/OutcomeBar.jsx":"b35c137942eb","components/feedback/VoteBadge.jsx":"53c98fb0d6f3","components/navigation/CandidateRail.jsx":"618e84016703","components/navigation/ModeSwitch.jsx":"ee23612cb8e5","components/navigation/PanelNav.jsx":"aabd48f9c5d1","ui_kits/empreinte-politique/CandidateProfile.jsx":"85279604a222","ui_kits/empreinte-politique/GroupProfile.jsx":"e468c67f0da5","ui_kits/empreinte-politique/HomeView.jsx":"21521246fd0e","ui_kits/empreinte-politique/data.js":"8ddf89f0ad87"},"inlinedExternals":[],"unexposedExports":[]} */

(() => {

const __ds_ns = (window.EmpreintePolitiqueDesignSystem_0817cb = window.EmpreintePolitiqueDesignSystem_0817cb || {});

const __ds_scope = {};

(__ds_ns.__errors = __ds_ns.__errors || []);

// components/core/Icon.jsx
try { (() => {
const PATHS = {
  list: '<path d="M7 5h9"/><path d="M7 10h9"/><path d="M7 15h9"/><circle cx="4" cy="5" r="1"/><circle cx="4" cy="10" r="1"/><circle cx="4" cy="15" r="1"/>',
  stethoscope: '<path d="M5 3v5a3 3 0 0 0 6 0V3"/><path d="M8 13v1a3 3 0 0 0 6 0v-1"/><path d="M14 13a2 2 0 1 0 0-4 2 2 0 0 0 0 4Z"/><path d="M5 3H3"/><path d="M11 3H9"/>',
  leaf: '<path d="M16 4c-5 0-9 2.5-11 8 4 2 8 1 11-2 2-2 2-4 0-6Z"/><path d="M7 11c1.5-.5 3.5-2 5-4"/>',
  wallet: '<path d="M3 6.5A1.5 1.5 0 0 1 4.5 5h9A1.5 1.5 0 0 1 15 6.5v7A1.5 1.5 0 0 1 13.5 15h-9A1.5 1.5 0 0 1 3 13.5v-7Z"/><path d="M15 8h2v4h-2a2 2 0 1 1 0-4Z"/>',
  graduation: '<path d="m2 7.5 8-4 8 4-8 4-8-4Z"/><path d="M5 9.5V13c0 1.5 2.2 2.5 5 2.5s5-1 5-2.5V9.5"/><path d="M18 7.5V13"/>',
  shield: '<path d="M10 3 4.5 5v4.5c0 3.3 2.3 5.8 5.5 7 3.2-1.2 5.5-3.7 5.5-7V5L10 3Z"/>',
  building: '<path d="M3 17h14"/><path d="M5 17V8l5-3 5 3v9"/><path d="M8 11h.01"/><path d="M12 11h.01"/><path d="M8 14h.01"/><path d="M12 14h.01"/>',
  globe: '<circle cx="10" cy="10" r="7"/><path d="M3.5 10h13"/><path d="M10 3c2 2 3 4.3 3 7s-1 5-3 7c-2-2-3-4.3-3-7s1-5 3-7Z"/>',
  handshake: '<path d="M7.5 6 10 8.2a1.8 1.8 0 0 0 2.4 0L14 7"/><path d="m3 8 3-3 3.2 2.7"/><path d="m17 8-3-3-3.2 2.7"/><path d="m6.5 10.5 2 2a1.2 1.2 0 0 0 1.7 0l.2-.2"/><path d="m8.8 12.6 1.4 1.4a1.2 1.2 0 0 0 1.7 0l.3-.3"/><path d="m11 13.8.8.8a1.2 1.2 0 0 0 1.7 0L16 12"/>',
  briefcase: '<rect x="3" y="6" width="14" height="10" rx="1"/><path d="M7 6V4.8A1.8 1.8 0 0 1 8.8 3h2.4A1.8 1.8 0 0 1 13 4.8V6"/><path d="M3 10h14"/>',
  fileText: '<path d="M6 3.5h5l3 3V16a1 1 0 0 1-1 1H6a1 1 0 0 1-1-1v-11a1 1 0 0 1 1-1Z"/><path d="M11 3.5V7h3"/><path d="M7 10h6"/><path d="M7 13h6"/>',
  ballot: '<path d="M4 7h12v10H4z"/><path d="m7 4 3 3 4-4"/>',
  database: '<ellipse cx="10" cy="5" rx="6" ry="2.5"/><path d="M4 5v5c0 1.4 2.7 2.5 6 2.5s6-1.1 6-2.5V5"/><path d="M4 10v5c0 1.4 2.7 2.5 6 2.5s6-1.1 6-2.5v-5"/>',
  messages: '<path d="M5 14H3.5A1.5 1.5 0 0 1 2 12.5v-6A1.5 1.5 0 0 1 3.5 5h8A1.5 1.5 0 0 1 13 6.5V8"/><path d="M6 8h4"/><path d="M6 11h3"/><path d="M9 10.5A1.5 1.5 0 0 1 10.5 9H16a1.5 1.5 0 0 1 1.5 1.5V14a1.5 1.5 0 0 1-1.5 1.5h-3.8L9 18v-3.5Z"/>',
  scale: '<path d="M10 4v12"/><path d="M5 6h10"/><path d="m5 6-2.5 4h5L5 6Z"/><path d="m15 6-2.5 4h5L15 6Z"/><path d="M7 17h6"/>',
  'kpi-anciennete': '<path d="M5 3h10M5 17h10M6 3c0 4 3 5 4 6 1-1 4-2 4-6M6 17c0-4 3-5 4-6 1 1 4 2 4 6"/>',
  'kpi-responsabilites': '<path d="M3 17h14M4 17V9l6-4 6 4v8M8 17v-5h4v5"/>',
  'kpi-vote': '<path d="M3 8h14v9H3z"/><path d="M7 8V5a3 3 0 0 1 6 0v3M10 11v3"/>',
  'kpi-theme': '<path d="M4 4h6l6 6-6 6-6-6z"/><circle cx="7" cy="7" r="1" fill="currentColor" stroke="none"/>'
};
function Icon(props) {
  const name = props.name;
  const size = props.size || 20;
  const body = PATHS[name];
  if (!body) return null;
  return React.createElement('svg', {
    viewBox: '0 0 20 20',
    width: size,
    height: size,
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.6,
    strokeLinecap: 'round',
    strokeLinejoin: 'round',
    'aria-hidden': 'true',
    style: {
      display: 'block',
      ...props.style
    },
    dangerouslySetInnerHTML: {
      __html: body
    }
  });
}
Object.assign(__ds_scope, { Icon });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Icon.jsx", error: String((e && e.message) || e) }); }

// components/core/SectionKicker.jsx
try { (() => {
function SectionKicker(props) {
  return React.createElement('p', {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: '11px',
      textTransform: 'uppercase',
      letterSpacing: '0.08em',
      color: props.inverse ? 'var(--text-inverse)' : 'var(--muted)',
      margin: 0
    }
  }, props.children);
}
Object.assign(__ds_scope, { SectionKicker });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/SectionKicker.jsx", error: String((e && e.message) || e) }); }

// components/core/Tag.jsx
try { (() => {
function Tag(props) {
  const variant = props.variant || 'default';
  const base = {
    display: 'inline-flex',
    alignItems: 'center',
    gap: '6px',
    border: '1px solid var(--line)',
    borderRadius: '999px',
    background: 'var(--bg)',
    padding: '2px 11px',
    fontFamily: 'var(--font-ui)',
    fontSize: 'var(--text-14)',
    color: 'var(--text)'
  };
  const styles = {
    default: base,
    pill: {
      ...base,
      cursor: 'pointer'
    },
    active: {
      ...base,
      background: 'var(--accent-soft)',
      borderColor: '#C4B8A4',
      color: 'var(--text)',
      fontWeight: 600,
      cursor: 'pointer'
    },
    inverse: {
      ...base,
      borderRadius: '0px',
      border: '1px solid var(--text-inverse)',
      background: 'transparent',
      color: 'var(--text-inverse)'
    }
  };
  const Tag_ = props.as === 'button' ? 'button' : 'span';
  return React.createElement(Tag_, {
    onClick: props.onClick,
    style: {
      ...(styles[variant] || base),
      ...(Tag_ === 'button' ? {
        fontFamily: 'inherit',
        cursor: 'pointer'
      } : {})
    }
  }, props.icon, props.children);
}
Object.assign(__ds_scope, { Tag });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/core/Tag.jsx", error: String((e && e.message) || e) }); }

// components/data/KpiCard.jsx
try { (() => {
const TINTS = ['transparent', 'var(--flag)', 'var(--accent-soft)', 'var(--highlight)'];
function KpiCard(props) {
  const [flipped, setFlipped] = React.useState(false);
  const tint = TINTS[props.tint || 0] || 'transparent';
  const isDark = tint === 'transparent';
  return React.createElement('button', {
    type: 'button',
    onClick: () => setFlipped(f => !f),
    style: {
      textAlign: 'left',
      font: 'inherit',
      color: 'inherit',
      background: tint,
      border: 0,
      borderRight: '2px solid var(--line)',
      padding: '16px',
      display: 'block',
      width: '100%',
      cursor: 'pointer',
      minHeight: '170px'
    }
  }, !flipped ? React.createElement('div', {
    style: {
      display: 'flex',
      flexDirection: 'column',
      height: '100%',
      justifyContent: 'space-between'
    }
  }, React.createElement('div', {
    style: {
      color: 'var(--text)'
    }
  }, React.createElement(__ds_scope.Icon, {
    name: props.icon,
    size: 26
  })), React.createElement('div', null, React.createElement('div', {
    style: {
      fontSize: 'clamp(2rem,7vw,3.2rem)',
      letterSpacing: '-0.04em',
      fontFamily: 'var(--font-mono)',
      fontWeight: 700
    }
  }, props.value), React.createElement('div', {
    style: {
      fontFamily: 'var(--font-mono)',
      textTransform: 'uppercase',
      fontSize: '12px',
      marginTop: '4px'
    }
  }, props.label))) : React.createElement('div', {
    style: {
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'center',
      height: '100%',
      gap: '8px',
      background: 'var(--text)',
      color: 'var(--bg)',
      margin: '-16px',
      padding: '16px',
      minHeight: '170px'
    }
  }, React.createElement('p', {
    style: {
      margin: 0,
      fontSize: '13px'
    }
  }, props.explanation)));
}
Object.assign(__ds_scope, { KpiCard });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/KpiCard.jsx", error: String((e && e.message) || e) }); }

// components/data/ScopeBar.jsx
try { (() => {
function ScopeBar(props) {
  const pct = props.max ? Math.min(100, props.value / props.max * 100) : 0;
  return React.createElement('button', {
    type: 'button',
    onClick: props.onClick,
    'aria-pressed': !!props.active,
    style: {
      display: 'grid',
      gridTemplateColumns: 'minmax(92px,1fr) minmax(0,3fr) auto',
      gap: '8px',
      alignItems: 'center',
      width: '100%',
      textAlign: 'left',
      font: 'inherit',
      color: 'inherit',
      background: props.active ? 'var(--accent-soft)' : 'transparent',
      border: props.active ? '1px solid var(--accent)' : '1px solid transparent',
      padding: '3px 2px',
      cursor: props.onClick ? 'pointer' : 'default',
      opacity: props.dimmed ? 0.55 : 1
    }
  }, React.createElement('span', {
    style: {
      fontFamily: 'var(--font-mono)',
      fontWeight: 600,
      fontSize: '11px',
      textTransform: 'uppercase',
      overflow: 'hidden',
      textOverflow: 'ellipsis',
      whiteSpace: 'nowrap'
    }
  }, props.label), React.createElement('span', {
    style: {
      height: '11px',
      borderRadius: '2px',
      background: 'var(--line)',
      overflow: 'hidden',
      width: '100%',
      display: 'block'
    }
  }, React.createElement('span', {
    style: {
      display: 'block',
      height: '100%',
      width: `${pct}%`,
      background: props.color || 'var(--text)'
    }
  })), React.createElement('span', {
    style: {
      fontFamily: 'var(--font-mono)',
      fontWeight: 600,
      fontSize: '12px',
      minWidth: '2ch'
    }
  }, props.value));
}
Object.assign(__ds_scope, { ScopeBar });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/ScopeBar.jsx", error: String((e && e.message) || e) }); }

// components/feedback/OutcomeBar.jsx
try { (() => {
const OUTCOME_COLORS = {
  'adopté': 'var(--outcome-adopte)',
  'rejeté': 'var(--outcome-rejete)',
  'retiré': 'var(--outcome-retire)',
  'tombé': 'var(--outcome-tombe)',
  'irrecevable': 'var(--outcome-irrecevable)',
  'non_soutenu': 'var(--outcome-non-soutenu)'
};
function OutcomeBar(props) {
  const segments = props.segments || [];
  const total = segments.reduce((s, x) => s + x.count, 0) || 1;
  return React.createElement('div', null, React.createElement('div', {
    style: {
      display: 'flex',
      height: '10px',
      borderRadius: '2px',
      overflow: 'hidden',
      background: 'var(--line)',
      marginBottom: '9px'
    }
  }, segments.map(seg => React.createElement('div', {
    key: seg.key,
    onClick: () => props.onSelect && props.onSelect(seg.key),
    style: {
      flex: `${seg.count} 0 0`,
      background: OUTCOME_COLORS[seg.key] || 'var(--muted)',
      cursor: props.onSelect ? 'pointer' : 'default'
    }
  }))), React.createElement('div', {
    style: {
      display: 'flex',
      flexWrap: 'wrap',
      gap: '4px 12px',
      fontSize: '12px',
      color: 'var(--muted)'
    }
  }, segments.map(seg => React.createElement('span', {
    key: seg.key,
    style: {
      display: 'flex',
      alignItems: 'center',
      gap: '5px'
    }
  }, React.createElement('span', {
    style: {
      width: '8px',
      height: '8px',
      borderRadius: '1px',
      background: OUTCOME_COLORS[seg.key] || 'var(--muted)',
      display: 'inline-block'
    }
  }), `${seg.label} (${seg.count})`))));
}
Object.assign(__ds_scope, { OutcomeBar });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/OutcomeBar.jsx", error: String((e && e.message) || e) }); }

// components/feedback/VoteBadge.jsx
try { (() => {
const STYLES = {
  pour: {
    background: 'var(--badge-pour-bg)',
    borderColor: 'var(--vote-pour)',
    color: 'var(--vote-pour)',
    fontWeight: 600,
    borderStyle: 'solid'
  },
  contre: {
    background: 'var(--badge-contre-bg)',
    borderColor: 'var(--vote-contre)',
    color: 'var(--vote-contre)',
    fontWeight: 600,
    borderStyle: 'solid'
  },
  abstention: {
    background: 'var(--bg)',
    borderColor: 'var(--muted)',
    color: 'var(--muted)',
    borderStyle: 'dashed'
  },
  absent: {
    background: 'var(--bg)',
    borderColor: 'var(--line)',
    color: 'var(--muted)',
    borderStyle: 'solid'
  }
};
const LABELS = {
  pour: 'Pour',
  contre: 'Contre',
  abstention: 'Abstention',
  absent: 'Absent'
};
function VoteBadge(props) {
  const s = STYLES[props.position] || STYLES.absent;
  return React.createElement('span', {
    style: {
      display: 'inline-block',
      borderRadius: '4px',
      padding: '2px 9px',
      fontSize: '13px',
      letterSpacing: '0.01em',
      border: `1px ${s.borderStyle} ${s.borderColor}`,
      background: s.background,
      color: s.color,
      fontWeight: s.fontWeight || 400,
      fontFamily: 'var(--font-ui)'
    }
  }, props.label || LABELS[props.position] || props.position);
}
Object.assign(__ds_scope, { VoteBadge });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/feedback/VoteBadge.jsx", error: String((e && e.message) || e) }); }

// components/data/VoteCard.jsx
try { (() => {
const BORDER = {
  pour: 'var(--vote-pour)',
  contre: 'var(--vote-contre)',
  abstention: 'var(--muted)',
  absent: 'var(--line)'
};
function VoteCard(props) {
  return React.createElement('div', {
    style: {
      border: '1px solid var(--line)',
      borderRadius: '10px',
      background: 'var(--surface)',
      padding: '11px',
      borderLeftWidth: '4px',
      borderLeftColor: BORDER[props.position] || 'var(--line)',
      borderLeftStyle: props.position === 'abstention' ? 'dashed' : 'solid'
    }
  }, React.createElement('p', {
    style: {
      margin: '0 0 4px',
      fontWeight: 600
    }
  }, props.title, React.createElement(__ds_scope.VoteBadge, {
    position: props.position
  })), React.createElement('p', {
    style: {
      margin: 0,
      fontSize: '13px',
      color: 'var(--muted)',
      fontFamily: 'var(--font-mono)'
    }
  }, props.meta));
}
Object.assign(__ds_scope, { VoteCard });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/data/VoteCard.jsx", error: String((e && e.message) || e) }); }

// components/navigation/CandidateRail.jsx
try { (() => {
function CandidateRail(props) {
  const items = props.items || [];
  return React.createElement('div', {
    role: 'tablist',
    'aria-label': props.ariaLabel,
    style: {
      display: 'flex',
      overflowX: 'auto',
      borderTop: '1px solid var(--line)',
      height: '48px'
    }
  }, items.map(it => React.createElement('button', {
    key: it.value,
    type: 'button',
    role: 'tab',
    disabled: it.disabled,
    'aria-selected': it.value === props.value,
    onClick: () => !it.disabled && props.onChange && props.onChange(it.value),
    style: {
      flex: '0 0 auto',
      height: '100%',
      padding: '0 16px',
      border: 0,
      borderRight: '2px solid var(--line)',
      background: it.value === props.value ? 'var(--text)' : 'transparent',
      color: it.value === props.value ? '#fff' : 'var(--text)',
      fontFamily: 'var(--font-mono)',
      fontSize: '12px',
      textTransform: 'uppercase',
      textDecoration: it.disabled ? 'line-through' : 'none',
      opacity: it.disabled ? 0.5 : 1,
      cursor: it.disabled ? 'not-allowed' : 'pointer'
    }
  }, it.label)));
}
Object.assign(__ds_scope, { CandidateRail });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/CandidateRail.jsx", error: String((e && e.message) || e) }); }

// components/navigation/ModeSwitch.jsx
try { (() => {
function ModeSwitch(props) {
  const options = props.options || [];
  return React.createElement('div', {
    role: 'group',
    'aria-label': props.ariaLabel,
    style: {
      display: 'flex',
      minHeight: '48px',
      border: '2px solid var(--line)',
      width: 'max-content'
    }
  }, options.map((opt, i) => React.createElement('button', {
    key: opt.value,
    type: 'button',
    'aria-pressed': opt.value === props.value,
    onClick: () => props.onChange && props.onChange(opt.value),
    style: {
      minHeight: '48px',
      padding: '0 20px',
      border: 0,
      borderRight: i < options.length - 1 ? '1px solid var(--line)' : 0,
      background: opt.value === props.value ? 'var(--text)' : 'transparent',
      color: opt.value === props.value ? 'var(--bg)' : 'var(--text)',
      fontFamily: 'var(--font-mono)',
      fontSize: '11px',
      textTransform: 'uppercase',
      cursor: 'pointer'
    }
  }, opt.label)));
}
Object.assign(__ds_scope, { ModeSwitch });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/ModeSwitch.jsx", error: String((e && e.message) || e) }); }

// components/navigation/PanelNav.jsx
try { (() => {
function PanelNav(props) {
  const items = props.items || [];
  return React.createElement('nav', {
    style: {
      position: props.fixed ? 'fixed' : 'static',
      left: 0,
      right: 0,
      bottom: 0,
      display: 'grid',
      gridTemplateColumns: `repeat(${items.length}, 1fr)`,
      borderTop: '2px solid var(--line)',
      background: 'var(--bg)'
    }
  }, items.map(it => React.createElement('button', {
    key: it.value,
    type: 'button',
    onClick: () => props.onChange && props.onChange(it.value),
    style: {
      height: '64px',
      border: 0,
      borderRight: '1px solid var(--line)',
      background: it.value === props.value ? 'var(--highlight)' : 'transparent',
      color: 'var(--text)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      justifyContent: 'center',
      gap: '3px',
      cursor: 'pointer'
    }
  }, React.createElement(__ds_scope.Icon, {
    name: it.icon,
    size: 20
  }), React.createElement('small', {
    style: {
      fontSize: '9px',
      textTransform: 'uppercase',
      fontFamily: 'var(--font-ui)'
    }
  }, it.label))));
}
Object.assign(__ds_scope, { PanelNav });
})(); } catch (e) { __ds_ns.__errors.push({ path: "components/navigation/PanelNav.jsx", error: String((e && e.message) || e) }); }

// ui_kits/empreinte-politique/CandidateProfile.jsx
try { (() => {
function CandidateProfile(props) {
  const {
    KpiCard,
    VoteCard,
    OutcomeBar,
    ScopeBar,
    PanelNav,
    Tag
  } = window.EmpreintePolitiqueDesignSystem_0817cb;
  const c = props.candidat;
  const [panel, setPanel] = React.useState('votes');
  const tints = [0, 1, 2, 3];
  return React.createElement('div', null, React.createElement('div', {
    style: {
      minHeight: '42vh',
      display: 'grid',
      alignContent: 'end',
      padding: 'clamp(16px,5vw,64px)',
      borderBottom: '2px solid var(--line)',
      color: 'var(--bg)',
      background: 'var(--text)'
    }
  }, React.createElement('p', {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: '11px',
      textTransform: 'uppercase',
      margin: '0 0 8px',
      opacity: 0.7
    }
  }, c.groupe), React.createElement('h2', {
    style: {
      color: 'var(--bg)',
      fontSize: 'clamp(3rem,10vw,7rem)',
      lineHeight: 0.85,
      maxWidth: '9ch',
      textTransform: 'uppercase',
      margin: 0
    }
  }, c.nom), React.createElement('div', {
    style: {
      display: 'flex',
      gap: '8px',
      marginTop: '12px'
    }
  }, React.createElement(Tag, {
    variant: 'inverse'
  }, c.parti), c.profession && React.createElement(Tag, {
    variant: 'inverse'
  }, c.profession))), React.createElement('div', {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(6,1fr)',
      borderBottom: '2px solid var(--line)'
    }
  }, React.createElement('div', {
    style: {
      gridColumn: 'span 3'
    }
  }, React.createElement(KpiCard, {
    icon: 'kpi-anciennete',
    value: c.kpis.anciennete,
    label: 'Ancienneté du mandat',
    explanation: 'Mesure la durée, pas l\u2019implication.',
    tint: 0
  })), React.createElement('div', {
    style: {
      gridColumn: 'span 3'
    }
  }, React.createElement(KpiCard, {
    icon: 'kpi-responsabilites',
    value: c.kpis.responsabilites,
    label: 'Responsabilités',
    explanation: 'Fonctions dédupliquées par intitulé. Jamais un score.',
    tint: 1
  })), React.createElement('div', {
    style: {
      gridColumn: 'span 3'
    }
  }, React.createElement(KpiCard, {
    icon: 'kpi-vote',
    value: c.kpis.votes,
    label: 'Votes de texte',
    explanation: 'Lecture la plus avancée retenue pour chaque texte.',
    tint: 2
  })), React.createElement('div', {
    style: {
      gridColumn: 'span 4'
    }
  }, React.createElement(KpiCard, {
    icon: 'kpi-theme',
    value: c.kpis.theme,
    label: 'Thème dominant',
    explanation: 'Aide de lecture par mots-clés, pas une position déclarée.',
    tint: 3
  }))), React.createElement('div', {
    style: {
      padding: 'clamp(1rem,4vw,3rem)'
    }
  }, panel === 'votes' && React.createElement('div', {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '10px'
    }
  }, React.createElement('h3', {
    style: {
      fontFamily: 'var(--font-display)',
      fontSize: 'clamp(1.6rem,4vw,2.4rem)',
      margin: '0 0 6px',
      textTransform: 'uppercase'
    }
  }, 'Votes de texte'), c.votes.map((v, i) => React.createElement(VoteCard, {
    key: i,
    title: v.titre,
    position: v.position,
    meta: v.meta
  }))), panel === 'textes' && React.createElement('div', null, React.createElement('h3', {
    style: {
      fontFamily: 'var(--font-display)',
      fontSize: 'clamp(1.6rem,4vw,2.4rem)',
      margin: '0 0 10px',
      textTransform: 'uppercase'
    }
  }, 'Textes & amendements'), React.createElement(OutcomeBar, {
    segments: c.outcomes
  }), React.createElement('div', {
    style: {
      marginTop: '18px',
      display: 'flex',
      flexDirection: 'column',
      gap: '8px'
    }
  }, c.scope.map((s, i) => React.createElement(ScopeBar, {
    key: i,
    ...s
  })))), panel === 'donnees' && React.createElement('p', {
    style: {
      color: 'var(--muted)',
      fontStyle: 'italic',
      maxWidth: '52ch'
    }
  }, 'Empreinte politique ne publie aucun taux individuel d\u2019assiduité, de présence ou d\u2019absence — un scrutin manqué ne décrit ni le travail parlementaire ni ses motifs.')), React.createElement(PanelNav, {
    items: [{
      value: 'votes',
      label: 'Votes',
      icon: 'ballot'
    }, {
      value: 'textes',
      label: 'Textes',
      icon: 'fileText'
    }, {
      value: 'donnees',
      label: 'Données',
      icon: 'database'
    }],
    value: panel,
    onChange: setPanel
  }));
}
window.CandidateProfile = CandidateProfile;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/empreinte-politique/CandidateProfile.jsx", error: String((e && e.message) || e) }); }

// ui_kits/empreinte-politique/GroupProfile.jsx
try { (() => {
function GroupProfile(props) {
  const {
    VoteBadge
  } = window.EmpreintePolitiqueDesignSystem_0817cb;
  const g = props.groupe;
  const kpiTints = ['var(--bg)', 'var(--accent-soft)', 'var(--highlight)', 'var(--flag)'];
  return React.createElement('div', null, React.createElement('div', {
    style: {
      minHeight: '42vh',
      display: 'grid',
      alignContent: 'end',
      padding: 'clamp(16px,5vw,64px)',
      borderBottom: '2px solid var(--line)',
      color: 'var(--bg)',
      background: 'var(--text)'
    }
  }, React.createElement('p', {
    style: {
      fontFamily: 'var(--font-mono)',
      fontSize: '11px',
      textTransform: 'uppercase',
      margin: '0 0 8px',
      opacity: 0.7
    }
  }, g.chambre), React.createElement('h2', {
    style: {
      color: 'var(--bg)',
      fontSize: 'clamp(2rem,5vw,3.2rem)',
      lineHeight: 0.9,
      maxWidth: '10ch',
      textTransform: 'uppercase',
      margin: 0
    }
  }, g.label)), React.createElement('div', {
    style: {
      padding: '13px 16px',
      borderBottom: '2px solid var(--line)',
      background: 'var(--flag)',
      font: "600 11px/1.5 var(--font-mono)"
    }
  }, 'Groupe parlementaire réel — pas un parti déclaré. Ratios publiés uniquement scrutin par scrutin, avec numérateur/dénominateur.'), React.createElement('div', {
    style: {
      display: 'grid',
      gridTemplateColumns: 'repeat(4,1fr)',
      borderBottom: '2px solid var(--line)'
    }
  }, g.kpis.map((k, i) => React.createElement('div', {
    key: i,
    style: {
      minHeight: '175px',
      padding: '16px',
      borderRight: i < 3 ? '2px solid var(--line)' : 0,
      background: kpiTints[i],
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'space-between'
    }
  }, React.createElement('b', {
    style: {
      display: 'block',
      font: '400 clamp(2rem,5vw,4rem)/0.9 var(--font-display)'
    }
  }, k.value), React.createElement('span', {
    style: {
      font: '600 10px/1.4 var(--font-mono)',
      textTransform: 'uppercase'
    }
  }, k.label)))), React.createElement('div', {
    style: {
      padding: 'clamp(1rem,4vw,3rem)'
    }
  }, React.createElement('h3', {
    style: {
      fontFamily: 'var(--font-display)',
      fontSize: 'clamp(1.6rem,4vw,2.4rem)',
      margin: '0 0 12px',
      textTransform: 'uppercase'
    }
  }, 'Scrutins couverts'), React.createElement('div', {
    style: {
      display: 'flex',
      flexDirection: 'column',
      gap: '10px'
    }
  }, g.votes.map((v, i) => React.createElement('div', {
    key: i,
    style: {
      border: '1px solid var(--line)',
      padding: '11px',
      display: 'flex',
      justifyContent: 'space-between',
      gap: '10px',
      alignItems: 'center'
    }
  }, React.createElement('span', null, v.titre), React.createElement(VoteBadge, {
    position: v.position
  }))))));
}
window.GroupProfile = GroupProfile;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/empreinte-politique/GroupProfile.jsx", error: String((e && e.message) || e) }); }

// ui_kits/empreinte-politique/HomeView.jsx
try { (() => {
function HomeView(props) {
  const items = props.mode === 'groups' ? window.EmpreintePolitiqueUiKitData.GROUPES : window.EmpreintePolitiqueUiKitData.CANDIDATS;
  return React.createElement('div', {
    className: 'home-stage',
    style: {
      minHeight: '66vh',
      display: 'grid',
      gridTemplateColumns: 'repeat(6,1fr)',
      borderBottom: '2px solid var(--line)'
    }
  }, React.createElement('div', {
    style: {
      gridColumn: '1 / -1',
      padding: 'clamp(16px,5vw,64px)',
      background: 'var(--text)',
      color: 'var(--bg)'
    }
  }, React.createElement('h2', {
    style: {
      maxWidth: '9.5ch',
      fontFamily: 'var(--font-display)',
      fontSize: 'clamp(1.8rem,4.2vw,3rem)',
      lineHeight: 0.92,
      textTransform: 'uppercase',
      letterSpacing: '-0.03em',
      margin: '0 0 10px'
    }
  }, 'Des faits, pas des scores.'), React.createElement('p', {
    style: {
      maxWidth: '52ch',
      margin: 0,
      fontSize: 'clamp(0.95rem,1.8vw,1.05rem)',
      lineHeight: 1.45
    }
  }, 'Mandats, votes, textes et interventions, chaque fait relié à sa source primaire. Aucun classement, aucune note.')), items.map((it, i) => React.createElement('button', {
    key: it.slug || it.id,
    type: 'button',
    onClick: () => props.onSelect(it.slug || it.id),
    style: {
      gridColumn: 'span 3',
      minHeight: '120px',
      padding: '13px',
      border: 0,
      borderRight: '1px solid var(--line)',
      borderBottom: '1px solid var(--line)',
      background: 'var(--bg)',
      color: 'var(--text)',
      textAlign: 'left',
      cursor: 'pointer',
      display: 'flex',
      flexDirection: 'column',
      justifyContent: 'space-between'
    }
  }, React.createElement('strong', {
    style: {
      fontFamily: 'var(--font-display)',
      fontSize: 'clamp(1rem,3vw,1.6rem)'
    }
  }, it.nom || it.label), React.createElement('small', {
    style: {
      fontFamily: 'var(--font-mono)'
    }
  }, it.parti || it.chambre))));
}
window.HomeView = HomeView;
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/empreinte-politique/HomeView.jsx", error: String((e && e.message) || e) }); }

// ui_kits/empreinte-politique/data.js
try { (() => {
const CANDIDATS = [{
  slug: 'jean-luc-melenchon',
  nom: 'Jean-Luc Mélenchon',
  parti: 'La France Insoumise (LFI)',
  profession: 'Ancien député',
  groupe: 'La France Insoumise - NUPES',
  kpis: {
    anciennete: '24 ans',
    responsabilites: '9',
    votes: '1 042',
    theme: 'Institutions'
  },
  votes: [{
    titre: "L'ensemble du projet de loi de finances 2026",
    position: 'contre',
    meta: 'Scrutin n°1122 · AN · 14/11/2025'
  }, {
    titre: "L'ensemble de la proposition de loi relative au logement",
    position: 'pour',
    meta: 'Scrutin n°998 · AN · 02/06/2025'
  }, {
    titre: "L'ensemble du projet de loi immigration",
    position: 'contre',
    meta: 'Scrutin n°874 · AN · 19/12/2024'
  }],
  outcomes: [{
    key: 'adopté',
    label: 'Adoptés',
    count: 21
  }, {
    key: 'rejeté',
    label: 'Rejetés',
    count: 34
  }, {
    key: 'retiré',
    label: 'Retirés',
    count: 6
  }, {
    key: 'tombé',
    label: 'Tombés',
    count: 4
  }, {
    key: 'irrecevable',
    label: 'Irrecevables',
    count: 12
  }, {
    key: 'non_soutenu',
    label: 'Non soutenus',
    count: 2
  }],
  scope: [{
    label: 'Majorité',
    value: 8,
    max: 40,
    color: 'var(--vote-pour)'
  }, {
    label: 'Opposition',
    value: 32,
    max: 40,
    color: 'var(--vote-contre)'
  }, {
    label: 'Non distingué',
    value: 3,
    max: 40,
    color: 'var(--muted)'
  }],
  themes: ['institutions', 'economie', 'social']
}, {
  slug: 'marine-le-pen',
  nom: 'Marine Le Pen',
  parti: 'Rassemblement National (RN)',
  profession: 'Ancienne députée européenne',
  groupe: 'Rassemblement National',
  kpis: {
    anciennete: '22 ans',
    responsabilites: '11',
    votes: '876',
    theme: 'Sécurité'
  },
  votes: [{
    titre: "L'ensemble du projet de loi de finances 2026",
    position: 'contre',
    meta: 'Scrutin n°1122 · AN · 14/11/2025'
  }, {
    titre: "L'ensemble du projet de loi immigration",
    position: 'pour',
    meta: 'Scrutin n°874 · AN · 19/12/2024'
  }, {
    titre: 'Motion de censure — gouvernement Bayrou',
    position: 'pour',
    meta: 'Scrutin n°812 · AN · 08/09/2025'
  }],
  outcomes: [{
    key: 'adopté',
    label: 'Adoptés',
    count: 14
  }, {
    key: 'rejeté',
    label: 'Rejetés',
    count: 41
  }, {
    key: 'retiré',
    label: 'Retirés',
    count: 3
  }, {
    key: 'tombé',
    label: 'Tombés',
    count: 2
  }, {
    key: 'irrecevable',
    label: 'Irrecevables',
    count: 9
  }, {
    key: 'non_soutenu',
    label: 'Non soutenus',
    count: 1
  }],
  scope: [{
    label: 'Majorité',
    value: 5,
    max: 38,
    color: 'var(--vote-pour)'
  }, {
    label: 'Opposition',
    value: 30,
    max: 38,
    color: 'var(--vote-contre)'
  }, {
    label: 'Non distingué',
    value: 3,
    max: 38,
    color: 'var(--muted)'
  }],
  themes: ['securite', 'europe_international', 'economie']
}, {
  slug: 'jordan-bardella',
  nom: 'Jordan Bardella',
  parti: 'Rassemblement National (RN)',
  profession: 'Ancien député européen',
  groupe: 'Rassemblement National',
  kpis: {
    anciennete: '7 ans',
    responsabilites: '4',
    votes: '312',
    theme: 'Europe / International'
  },
  votes: [{
    titre: "L'ensemble du projet de loi immigration",
    position: 'pour',
    meta: 'Scrutin n°874 · AN · 19/12/2024'
  }],
  outcomes: [{
    key: 'adopté',
    label: 'Adoptés',
    count: 3
  }, {
    key: 'rejeté',
    label: 'Rejetés',
    count: 8
  }, {
    key: 'retiré',
    label: 'Retirés',
    count: 1
  }, {
    key: 'tombé',
    label: 'Tombés',
    count: 0
  }, {
    key: 'irrecevable',
    label: 'Irrecevables',
    count: 2
  }, {
    key: 'non_soutenu',
    label: 'Non soutenus',
    count: 0
  }],
  scope: [{
    label: 'Majorité',
    value: 1,
    max: 14,
    color: 'var(--vote-pour)'
  }, {
    label: 'Opposition',
    value: 11,
    max: 14,
    color: 'var(--vote-contre)'
  }, {
    label: 'Non distingué',
    value: 2,
    max: 14,
    color: 'var(--muted)'
  }],
  themes: ['europe_international', 'securite']
}, {
  slug: 'bruno-retailleau',
  nom: 'Bruno Retailleau',
  parti: 'Les Républicains (LR)',
  profession: 'Ancien ministre de l\u2019Intérieur',
  groupe: 'Les Républicains',
  kpis: {
    anciennete: '18 ans',
    responsabilites: '13',
    votes: '654',
    theme: 'Sécurité'
  },
  votes: [{
    titre: "L'ensemble du projet de loi de finances 2026",
    position: 'pour',
    meta: 'Scrutin n°1122 · AN · 14/11/2025'
  }],
  outcomes: [{
    key: 'adopté',
    label: 'Adoptés',
    count: 19
  }, {
    key: 'rejeté',
    label: 'Rejetés',
    count: 22
  }, {
    key: 'retiré',
    label: 'Retirés',
    count: 4
  }, {
    key: 'tombé',
    label: 'Tombés',
    count: 1
  }, {
    key: 'irrecevable',
    label: 'Irrecevables',
    count: 6
  }, {
    key: 'non_soutenu',
    label: 'Non soutenus',
    count: 0
  }],
  scope: [{
    label: 'Majorité',
    value: 22,
    max: 30,
    color: 'var(--vote-pour)'
  }, {
    label: 'Opposition',
    value: 6,
    max: 30,
    color: 'var(--vote-contre)'
  }, {
    label: 'Non distingué',
    value: 2,
    max: 30,
    color: 'var(--muted)'
  }],
  themes: ['securite', 'institutions']
}];
const GROUPES = [{
  id: 'AN-SOC-16',
  label: 'Socialistes et apparentés',
  chambre: 'Assemblée nationale',
  membres: 66,
  kpis: [{
    value: '66',
    label: 'Membres éligibles'
  }, {
    value: '412',
    label: 'Scrutins couverts'
  }, {
    value: 'N/D',
    label: 'Cohésion moyenne'
  }, {
    value: '58',
    label: 'Textes portés'
  }],
  votes: [{
    titre: "L'ensemble du projet de loi de finances 2026",
    position: 'contre'
  }, {
    titre: "L'ensemble de la proposition de loi relative au logement",
    position: 'pour'
  }, {
    titre: "Motion de censure — gouvernement Bayrou",
    position: 'abstention'
  }]
}, {
  id: 'AN-RN-16',
  label: 'Rassemblement National',
  chambre: 'Assemblée nationale',
  membres: 124,
  kpis: [{
    value: '124',
    label: 'Membres éligibles'
  }, {
    value: '398',
    label: 'Scrutins couverts'
  }, {
    value: 'N/D',
    label: 'Cohésion moyenne'
  }, {
    value: '31',
    label: 'Textes portés'
  }],
  votes: [{
    titre: "L'ensemble du projet de loi immigration",
    position: 'pour'
  }, {
    titre: "L'ensemble du projet de loi de finances 2026",
    position: 'contre'
  }]
}];
})(); } catch (e) { __ds_ns.__errors.push({ path: "ui_kits/empreinte-politique/data.js", error: String((e && e.message) || e) }); }

__ds_ns.Icon = __ds_scope.Icon;

__ds_ns.SectionKicker = __ds_scope.SectionKicker;

__ds_ns.Tag = __ds_scope.Tag;

__ds_ns.KpiCard = __ds_scope.KpiCard;

__ds_ns.ScopeBar = __ds_scope.ScopeBar;

__ds_ns.VoteCard = __ds_scope.VoteCard;

__ds_ns.OutcomeBar = __ds_scope.OutcomeBar;

__ds_ns.VoteBadge = __ds_scope.VoteBadge;

__ds_ns.CandidateRail = __ds_scope.CandidateRail;

__ds_ns.ModeSwitch = __ds_scope.ModeSwitch;

__ds_ns.PanelNav = __ds_scope.PanelNav;

})();
