# Copyright 2025 LibreLane Contributors
# Adapted from OpenLane

source $::env(SCRIPTS_DIR)/openroad/common/io.tcl
source $::env(SCRIPTS_DIR)/openroad/common/set_global_connections.tcl
set_global_connections

# =============================================================================
# OVERRIDE CORE RING DIMENSIONS (Doubled Thickness)
# =============================================================================
set ::env(PDN_CORE_RING_VWIDTH)   7   ;# Vertical thickness
set ::env(PDN_CORE_RING_HWIDTH)   7   ;# Horizontal thickness
set ::env(PDN_CORE_RING_VSPACING) 5.0  ;# Gap between the VDD and VSS rings
set ::env(PDN_CORE_RING_HSPACING) 11.5 ;# Gap between the VDD and VSS rings
set ::env(PDN_CORE_RING_VOFFSET)  3.0 ;# Pushed further out to clear standard cells
set ::env(PDN_CORE_RING_HOFFSET)  3.0 ;# Pushed further out to clear standard cells

foreach pnet $::env(VDD_NETS) {
    set n [[ord::get_db_block] findNet $pnet]
    if {$n != "NULL"} { $n setSpecial; $n setSigType "POWER" }
}
foreach gnet $::env(GND_NETS) {
    set n [[ord::get_db_block] findNet $gnet]
    if {$n != "NULL"} { $n setSpecial; $n setSigType "GROUND" }
}

set secondary []
foreach vdd $::env(VDD_NETS) gnd $::env(GND_NETS) {
    if { $vdd != $::env(VDD_NET)} { lappend secondary $vdd }
    if { $gnd != $::env(GND_NET)} { lappend secondary $gnd }
}

set_voltage_domain -name CORE -power $::env(VDD_NET) -ground $::env(GND_NET) \
    -secondary_power $secondary

if { $::env(PDN_MULTILAYER) == 1 } {
    set arg_list [list]
    if { $::env(PDN_ENABLE_PINS) } { lappend arg_list -pins "$::env(PDN_VERTICAL_LAYER) $::env(PDN_HORIZONTAL_LAYER)" }

    define_pdn_grid -name stdcell_grid -starts_with POWER -voltage_domain CORE {*}$arg_list

    set arg_list [list]
    append_if_equals arg_list PDN_EXTEND_TO "core_ring" -extend_to_core_ring
    append_if_equals arg_list PDN_EXTEND_TO "boundary" -extend_to_boundary

    add_pdn_stripe -grid stdcell_grid -layer $::env(PDN_VERTICAL_LAYER) -width $::env(PDN_VWIDTH) \
        -pitch $::env(PDN_VPITCH) -offset $::env(PDN_VOFFSET) -spacing $::env(PDN_VSPACING) \
        -starts_with POWER {*}$arg_list

    add_pdn_stripe -grid stdcell_grid -layer $::env(PDN_HORIZONTAL_LAYER) -width $::env(PDN_HWIDTH) \
        -pitch $::env(PDN_HPITCH) -offset $::env(PDN_HOFFSET) -spacing $::env(PDN_HSPACING) \
        -starts_with POWER {*}$arg_list

    add_pdn_connect -grid stdcell_grid -layers "$::env(PDN_VERTICAL_LAYER) $::env(PDN_HORIZONTAL_LAYER)"
} else {
    set arg_list [list]
    if { $::env(PDN_ENABLE_PINS) } { lappend arg_list -pins "$::env(PDN_VERTICAL_LAYER)" }

    define_pdn_grid -name stdcell_grid -starts_with POWER -voltage_domain CORE {*}$arg_list

    set arg_list [list]
    append_if_equals arg_list PDN_EXTEND_TO "core_ring" -extend_to_core_ring
    append_if_equals arg_list PDN_EXTEND_TO "boundary" -extend_to_boundary

    add_pdn_stripe -grid stdcell_grid -layer $::env(PDN_VERTICAL_LAYER) -width $::env(PDN_VWIDTH) \
        -pitch $::env(PDN_VPITCH) -offset $::env(PDN_VOFFSET) -spacing $::env(PDN_VSPACING) \
        -starts_with POWER {*}$arg_list
}

if { $::env(PDN_ENABLE_RAILS) == 1 } {
    add_pdn_stripe -grid stdcell_grid -layer $::env(PDN_RAIL_LAYER) -width $::env(PDN_RAIL_WIDTH) -followpins
    add_pdn_connect -grid stdcell_grid -layers "$::env(PDN_RAIL_LAYER) $::env(PDN_VERTICAL_LAYER)"
}

if { $::env(PDN_CORE_RING) == 1 } {
    if { $::env(PDN_MULTILAYER) == 1 } {
        set arg_list [list]
        append_if_flag arg_list PDN_CORE_RING_ALLOW_OUT_OF_DIE -allow_out_of_die
        append_if_flag arg_list PDN_CORE_RING_CONNECT_TO_PADS -connect_to_pads
        append_if_equals arg_list PDN_EXTEND_TO "boundary" -extend_to_boundary

        set pdn_core_vertical_layer $::env(PDN_VERTICAL_LAYER)
        set pdn_core_horizontal_layer $::env(PDN_HORIZONTAL_LAYER)
        if { [info exists ::env(PDN_CORE_VERTICAL_LAYER)] } { set pdn_core_vertical_layer $::env(PDN_CORE_VERTICAL_LAYER) }
        if { [info exists ::env(PDN_CORE_HORIZONTAL_LAYER)] } { set pdn_core_horizontal_layer $::env(PDN_CORE_HORIZONTAL_LAYER) }

        add_pdn_ring -grid stdcell_grid -layers "$pdn_core_vertical_layer $pdn_core_horizontal_layer" \
            -widths "$::env(PDN_CORE_RING_VWIDTH) $::env(PDN_CORE_RING_HWIDTH)" \
            -spacings "$::env(PDN_CORE_RING_VSPACING) $::env(PDN_CORE_RING_HSPACING)" \
            -core_offset "$::env(PDN_CORE_RING_VOFFSET) $::env(PDN_CORE_RING_HOFFSET)" {*}$arg_list

        if { [info exists ::env(PDN_CORE_VERTICAL_LAYER)] } { add_pdn_connect -grid stdcell_grid -layers "$::env(PDN_CORE_VERTICAL_LAYER) $::env(PDN_HORIZONTAL_LAYER)" }
        if { [info exists ::env(PDN_CORE_HORIZONTAL_LAYER)] } { add_pdn_connect -grid stdcell_grid -layers "$::env(PDN_CORE_HORIZONTAL_LAYER) $::env(PDN_VERTICAL_LAYER)" }
        if { [info exists ::env(PDN_CORE_VERTICAL_LAYER)] && [info exists ::env(PDN_CORE_HORIZONTAL_LAYER)] } { add_pdn_connect -grid stdcell_grid -layers "$::env(PDN_CORE_VERTICAL_LAYER) $::env(PDN_CORE_HORIZONTAL_LAYER)" }
    } else {
        throw APPLICATION "PDN_CORE_RING cannot be used when PDN_MULTILAYER is set to false."
    }
}

# =============================================================================
# A37 PADFRAME MULTI-BRIDGE (Bottom VSS TOP-CONNECTED, OTHERS midpoint)
# =============================================================================
set ::_PG_BRIDGE_W_UM   5.0
set ::_PG_M2_LAND_UM     2.4
set ::_PG_M3_EDGE_UM     0.20

proc _pg_template_path {} {
    if {[info exists ::env(FP_DEF_TEMPLATE)] && [file readable $::env(FP_DEF_TEMPLATE)]} { return $::env(FP_DEF_TEMPLATE) }
    if {![info exists ::env(PDN_CFG)]} { error "power-bridge: cannot locate template (no FP_DEF_TEMPLATE, no PDN_CFG)" }
    set cfgdir [file dirname $::env(PDN_CFG)]
    set cfg [file join $cfgdir config_core.yaml]
    if {[file readable $cfg]} {
        set fh [open $cfg r]; set txt [read $fh]; close $fh
        if {[regexp {FP_DEF_TEMPLATE:\s*dir::(\S+)} $txt -> rel]} {
            set p [file normalize [file join $cfgdir $rel]]
            if {[file readable $p]} { return $p }
        }
    }
    error "power-bridge: could not resolve FP_DEF_TEMPLATE from $cfg"
}

proc _pg_template_pin_rows {net_name} {
    set fh [open [_pg_template_path] r]
    set tdbu 1000; set rows {}; set in 0
    while {[gets $fh line] >= 0} {
        if {[regexp {UNITS\s+DISTANCE\s+MICRONS\s+(\d+)} $line -> u]} { set tdbu $u; continue }
        if {[regexp {^-\s+(\S+)\s+\+\s+NET\s+(\S+)} $line -> pn nn]} { set in [expr {$nn eq $net_name}]; continue }
        if {$in} {
            if {[regexp {LAYER\s+Metal2\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)\s+\(\s*(-?\d+)\s+(-?\d+)\s*\)} $line -> x1 y1 x2 y2]} {
                lappend rows [list $y1 $y2 $x2]
            }
            if {[string first ";" $line] >= 0} { set in 0 }
        }
    }
    close $fh
    return [list $tdbu $rows]
}

proc _pg_west_leg {net} {
    set best ""
    foreach sw [$net getSWires] {
        foreach box [$sw getWires] {
            if {[$box isVia]} { continue }
            set ly [$box getTechLayer]
            if {$ly eq "NULL" || [$ly getName] ne "Metal2"} { continue }
            set w [expr {[$box xMax] - [$box xMin]}]; set h [expr {[$box yMax] - [$box yMin]}]
            if {$h < 5 * $w} { continue }
            if {$best eq "" || [$box xMin] < [lindex $best 0]} {
                set best [list [$box xMin] [$box xMax]]
            }
        }
    }
    return $best
}

proc _pg_make_stack_via {block name m2 v2 m3 nrow ncol} {
    set v [odb::dbVia_create $block $name]
    $v setViaGenerateRule [[$block getTech] findViaGenerateRule "Via2_GEN_HH"]
    set cs [expr {($nrow >= 4 || $ncol >= 4) ? 720 : 520}]
    set p [$v getViaParams]
    $p setBottomLayer $m2; $p setCutLayer $v2; $p setTopLayer $m3
    $p setXCutSize 520; $p setYCutSize 520
    $p setXCutSpacing $cs; $p setYCutSpacing $cs
    $p setXBottomEnclosure 120; $p setYBottomEnclosure 120
    $p setXTopEnclosure 120; $p setYTopEnclosure 120
    $p setNumCutRows $nrow; $p setNumCutCols $ncol
    $v setViaParams $p
    return $v
}

proc _pg_build_power_bridges {} {
    if {[info exists ::_PG_DONE]} { return }
    set ::_PG_DONE 1

    set block [ord::get_db_block]; set tech [ord::get_db_tech]; set dbu [$block getDbUnitsPerMicron]
    set m2 [$tech findLayer Metal2]; set v2 [$tech findLayer Via2]; set m3 [$tech findLayer Metal3]
    if {$m2 eq "NULL" || $v2 eq "NULL" || $m3 eq "NULL"} { error "power-bridge: Metal2/Via2/Metal3 not found in tech" }

    set bw [expr {int($::_PG_BRIDGE_W_UM * $dbu)}]; set hw [expr {$bw / 2}]
    set landx [expr {int($::_PG_M2_LAND_UM * $dbu)}]
    set m3x0 [expr {int($::_PG_M3_EDGE_UM * $dbu)}]
    set xcw [expr {$landx / 2}]

    # Create distinct MAXIMIZED via arrays based on overlap area
    set pad_via [_pg_make_stack_via $block PG_V2_PAD $m2 $v2 $m3 8 4]
    set ring_via [_pg_make_stack_via $block PG_V2_RING $m2 $v2 $m3 8 11]

    set vdd [$block findNet VDD]; set vss [$block findNet VSS]
    if {$vdd eq "NULL" || $vss eq "NULL"} { error "power-bridge: VDD/VSS net missing" }

    set vss_leg [_pg_west_leg $vss]; set vdd_leg [_pg_west_leg $vdd]
    if {$vss_leg eq "" || $vdd_leg eq ""} { error "power-bridge: could not find VDD/VSS core-ring legs" }

    lassign $vss_leg vssL vssR
    lassign $vdd_leg vddL vddR

    # =========================================================================
    # VSS MULTI-BRIDGE (First Pad = Top-Connected, Others = Midpoint)
    # =========================================================================
    lassign [_pg_template_pin_rows VSS] tdbu vss_rows
    set sc [expr {double($dbu) / $tdbu}]
    set sw_vss [odb::dbSWire_create $vss "ROUTED"]

    # Sort vss_rows by y1 ascending so index 0 is guaranteed to be the bottom-most pad
    set vss_rows [lsort -integer -index 0 $vss_rows]

    set vss_min_y 1000000000; set vss_max_y 0

    if {[llength $vss_rows] > 0} {
        # 1. Handle the first VSS pad at the top edge to clear the southwest corner
        set first_r [lindex $vss_rows 0]
        lassign $first_r y1 y2 x2
        set y1_dbu [expr {int($y1 * $sc)}]; set y2_dbu [expr {int($y2 * $sc)}]
        if {$y1_dbu < $vss_min_y} { set vss_min_y $y1_dbu }
        if {$y2_dbu > $vss_max_y} { set vss_max_y $y2_dbu }
        
        set cy_first [expr {$y2_dbu - $hw}]
        odb::dbSBox_create $sw_vss $m3 $m3x0 [expr {$cy_first - $hw}] $vssR [expr {$cy_first + $hw}] "STRIPE"
        odb::dbSBox_create $sw_vss $pad_via $xcw $cy_first "STRIPE"
        odb::dbSBox_create $sw_vss $ring_via [expr {($vssL + $vssR) / 2}] $cy_first "STRIPE"

        # 2. Handle the rest of the VSS pads normally (midpoint)
        foreach r [lrange $vss_rows 1 end] {
            lassign $r y1 y2 x2
            set y1_dbu [expr {int($y1 * $sc)}]; set y2_dbu [expr {int($y2 * $sc)}]
            if {$y1_dbu < $vss_min_y} { set vss_min_y $y1_dbu }
            if {$y2_dbu > $vss_max_y} { set vss_max_y $y2_dbu }
            
            set cy_row [expr {int(($y1_dbu + $y2_dbu) / 2)}]
            odb::dbSBox_create $sw_vss $m3 $m3x0 [expr {$cy_row - $hw}] $vssR [expr {$cy_row + $hw}] "STRIPE"
            odb::dbSBox_create $sw_vss $pad_via $xcw $cy_row "STRIPE"
            odb::dbSBox_create $sw_vss $ring_via [expr {($vssL + $vssR) / 2}] $cy_row "STRIPE"
        }
    }
    if {$vss_min_y < 1000000000} {
        odb::dbSBox_create $sw_vss $m2 0 $vss_min_y $landx $vss_max_y "STRIPE"
    }

    # =========================================================================
    # VDD MULTI-BRIDGE (Sort by Y, top-most pad = Top Edge Connected)
    # =========================================================================
    lassign [_pg_template_pin_rows VDD] tdbu vdd_rows
    set sw_vdd [odb::dbSWire_create $vdd "ROUTED"]

    # Sort vdd_rows by y1 ascending so index end is the northernmost pad
    set vdd_rows [lsort -integer -index 0 $vdd_rows]

    set vdd_min_y 1000000000; set vdd_max_y 0

    if {[llength $vdd_rows] > 0} {
        # 1. Handle the lower/intermediate VDD pads normally (midpoint)
        foreach r [lrange $vdd_rows 0 end-1] {
            lassign $r y1 y2 x2
            set y1_dbu [expr {int($y1 * $sc)}]; set y2_dbu [expr {int($y2 * $sc)}]
            if {$y1_dbu < $vdd_min_y} { set vdd_min_y $y1_dbu }
            if {$y2_dbu > $vdd_max_y} { set vdd_max_y $y2_dbu }
            
            set cy_row [expr {int(($y1_dbu + $y2_dbu) / 2)}]
            odb::dbSBox_create $sw_vdd $m3 $m3x0 [expr {$cy_row - $hw}] $vddR [expr {$cy_row + $hw}] "STRIPE"
            odb::dbSBox_create $sw_vdd $pad_via $xcw $cy_row "STRIPE"
            odb::dbSBox_create $sw_vdd $ring_via [expr {($vddL + $vddR) / 2}] $cy_row "STRIPE"
        }

       # 2. Handle the top-most VDD pad at its top edge
        set top_r [lindex $vdd_rows end]
        lassign $top_r y1 y2 x2
        set y1_dbu [expr {int($y1 * $sc)}]; set y2_dbu [expr {int($y2 * $sc)}]
        if {$y1_dbu < $vdd_min_y} { set vdd_min_y $y1_dbu }
        if {$y2_dbu > $vdd_max_y} { set vdd_max_y $y2_dbu }
        
        set cy_top [expr {$y2_dbu - $hw}]
        odb::dbSBox_create $sw_vdd $m3 $m3x0 [expr {$cy_top - $hw}] $vddR [expr {$cy_top + $hw}] "STRIPE"
        odb::dbSBox_create $sw_vdd $pad_via $xcw $cy_top "STRIPE"
        odb::dbSBox_create $sw_vdd $ring_via [expr {($vddL + $vddR) / 2}] $cy_top "STRIPE"
    }
    odb::dbSBox_create $sw_vdd $m2 0 $vdd_min_y $landx $vdd_max_y "STRIPE"
}

if {[info commands pdngen] ne "" && [info commands _pg_pdngen_real] eq ""} {
    rename pdngen _pg_pdngen_real
    proc pdngen {args} {
        set rc [uplevel 1 [list _pg_pdngen_real {*}$args]]
        if {[catch {_pg_build_power_bridges} emsg]} { puts stderr "\[ERROR\] power-bridge builder failed: $emsg" }
        return $rc
    }
}