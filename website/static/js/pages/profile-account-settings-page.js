'use strict';

var $ = require('jquery');
var $osf = require('js/osfHelpers.js');
var accountSettings = require('js/accountSettings.js');
var passwordForms = require('js/passwordForms');
var profile = require('../profile.js');


$(function() {
    var ctx = window.contextVars;
    !!$('#accountInformation').length && new profile.AccountInformation('#accountInformation', ctx.accountUrls, ['edit']);

    var viewModel = new accountSettings.UserProfileViewModel();
    $osf.applyBindings(viewModel, '#connectedEmails');
    viewModel.init();

    new passwordForms.ChangePassword('#changePassword');

    $osf.applyBindings(
        new accountSettings.DeactivateAccountViewModel(),
        '#deactivateAccount'
    );

    $osf.applyBindings(
        new accountSettings.ExportAccountViewModel(),
        '#exportAccount'
    );

    $osf.applyBindings(
        new accountSettings.ExternalIdentityViewModel(),
        '#externalIdentity'
    );

    $osf.applyBindings( new accountSettings.UpdateDefaultStorageLocation(),
        '#updateDefaultStorageLocation');
});
